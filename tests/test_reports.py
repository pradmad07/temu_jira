import pytest
from app.domain.enums import Priority, Category, Status
from app.services.reports import ReportService
from tests.helpers import report, user

def test_overview_empty_seed(c):
    overview = c.reports.overview()
    assert overview["total"] == 0
    assert overview["open"] == 0
    assert overview["critical"] == 0
    assert overview["resolved"] == 0
    assert overview["sla_violations"] == 0

def test_overview_with_incidents_and_lifecycle(c):
    # 1. Report P3 incident on SVC-DB
    inc1 = report(c, email="e1@itsm.local", service="SVC-DB", category="DATABASE")
    # 2. Report P1 critical incident on SVC-PAY
    inc2 = report(c, email="e2@itsm.local", service="SVC-PAY", category="APPLICATION")
    admin = user(c, "admin@itsm.local")
    c.incident_service.change_priority(admin, inc2.id, Priority.P1, "Critical payment down")

    overview = c.reports.overview()
    assert overview["total"] == 2
    assert overview["open"] == 2
    assert overview["critical"] == 1
    assert overview["resolved"] == 0

    # Assign and resolve inc1
    c.incident_service.assign_incident(admin, inc1.id, "U-T1")
    t1 = user(c, "t1@itsm.local")
    c.incident_service.acknowledge(t1, inc1.id)
    c.incident_service.start_investigation(t1, inc1.id)
    c.incident_service.resolve(t1, inc1.id, "Database query index created")

    overview_after = c.reports.overview()
    assert overview_after["total"] == 2
    assert overview_after["open"] == 1
    assert overview_after["critical"] == 1
    assert overview_after["resolved"] == 1

def test_overview_sla_violations(c):
    inc = report(c, email="e1@itsm.local", service="SVC-PAY", category="APPLICATION")
    c.incident_service.change_priority(user(c, "admin@itsm.local"), inc.id, Priority.P1, "Urgent")
    c.clock.advance(minutes=35)
    c.sla.scan()

    overview = c.reports.overview()
    assert overview["sla_violations"] == 1

def test_technician_workload_counts(c):
    admin = user(c, "admin@itsm.local")
    inc1 = report(c, email="e1@itsm.local", service="SVC-DB", category="DATABASE")
    inc2 = report(c, email="e2@itsm.local", service="SVC-DB", category="DATABASE")
    inc3 = report(c, email="e1@itsm.local", service="SVC-NET", category="NETWORK")

    # Assign 2 to Tina (U-T1) and 1 to Tom (U-T2)
    c.incident_service.assign_incident(admin, inc1.id, "U-T1")
    c.incident_service.assign_incident(admin, inc2.id, "U-T1")
    c.incident_service.assign_incident(admin, inc3.id, "U-T2")

    workload = c.reports.technician_workload()
    assert len(workload) >= 3  # Tina, Tom, Tara

    workload_map = {row[0]: row[1] for row in workload}
    assert workload_map["Tina DB"] == 2
    assert workload_map["Tom Net"] == 1
    assert workload_map["Tara Gen"] == 0

    # Ensure list is sorted descending by active count
    counts = [row[1] for row in workload]
    assert counts == sorted(counts, reverse=True)

def test_service_counts(c):
    report(c, email="e1@itsm.local", service="SVC-PAY", category="APPLICATION")
    report(c, email="e2@itsm.local", service="SVC-PAY", category="APPLICATION")
    report(c, email="e1@itsm.local", service="SVC-DB", category="DATABASE")

    service_counts = c.reports.service_counts()
    count_map = {row[0]: row[1] for row in service_counts}

    assert count_map["Payment App"] == 2
    assert count_map["Database"] == 1
    assert count_map["Email"] == 0

    counts = [row[1] for row in service_counts]
    assert counts == sorted(counts, reverse=True)
    
    
def test_overview_sla_violations_excludes_warnings(c):
    """A warning-only incident does not count as an SLA violation."""
    inc = report(c, email="e1@itsm.local", service="SVC-DB", category="DATABASE")
    c.incident_service.change_priority(user(c, "admin@itsm.local"), inc.id, Priority.P1, "Urgent")
    # SVC-DB default P1 response = 5 min; 75% threshold = 3:45. Advance 4 min: WARNING only.
    c.clock.advance(minutes=4)
    c.sla.scan()

    kinds = [k for k, _ in c.violations.list_for_incident(inc.id)]
    assert any("WARNING" in k for k in kinds)
    assert not any("VIOLATION" in k for k in kinds)

    assert c.reports.overview()["sla_violations"] == 0


def test_overview_sla_violations_counts_one_violation(c):
    """One RESPONSE_VIOLATION on one incident -> sla_violations == 1."""
    inc = report(c, email="e1@itsm.local", service="SVC-DB", category="DATABASE")
    c.incident_service.change_priority(user(c, "admin@itsm.local"), inc.id, Priority.P1, "Urgent")
    # 5-min response window passed; 30-min resolution window not yet.
    c.clock.advance(minutes=10)
    c.sla.scan()

    kinds = [k for k, _ in c.violations.list_for_incident(inc.id)]
    assert kinds.count("RESPONSE_VIOLATION") == 1
    assert "RESOLUTION_VIOLATION" not in kinds

    assert c.reports.overview()["sla_violations"] == 1


def test_overview_sla_violations_two_kinds_on_same_incident_count_once(c):
    """RESPONSE_VIOLATION + RESOLUTION_VIOLATION on the same incident -> still 1 (distinct incident)."""
    inc = report(c, email="e1@itsm.local", service="SVC-DB", category="DATABASE")
    c.incident_service.change_priority(user(c, "admin@itsm.local"), inc.id, Priority.P1, "Urgent")
    c.clock.advance(minutes=35)
    c.sla.scan()

    kinds = [k for k, _ in c.violations.list_for_incident(inc.id)]
    assert kinds.count("RESPONSE_VIOLATION") == 1
    assert kinds.count("RESOLUTION_VIOLATION") == 1
    assert "P1_ESCALATION" in kinds            # extra row, but must not count as a violation

    assert c.reports.overview()["sla_violations"] == 1


def test_report_service_works_without_db_attribute():
    """A fake repo with no _db proves ReportService only calls repository methods."""
    class FakeIncidentRepo:
        def __init__(self):
            self._items = []                   # a plain list, not a DB
        def count_total(self): return len(self._items)
        def count_by_status(self, statuses): return sum(1 for i in self._items if i.status in statuses)
        def count_critical(self): return sum(1 for i in self._items if i.priority == Priority.P1)
        def technician_workload(self): return []
        def counts_by_service(self): return []

    class FakeViolationRepo:
        def __init__(self, n): self._n = n
        def count_violated_incidents(self): return self._n

    svc = ReportService(FakeIncidentRepo(), violations=FakeViolationRepo(2))
    assert svc.overview() == {
        "total": 0, "open": 0, "critical": 0, "resolved": 0, "sla_violations": 2,
    }
