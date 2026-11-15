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
