import pytest
from app.domain.enums import Priority, Status, Role
from app.domain.events import EV_SLA_VIOLATED, EV_SLA_WARNING, EV_ESCALATED
from tests.helpers import report, user


def _p1_assigned_to_t1(c):
    """A P1 incident on the technician's queue, never acknowledged."""
    admin = user(c, "admin@itsm.local")
    t1 = user(c, "t1@itsm.local")
    inc = report(c, email="e1@itsm.local", service="SVC-PAY", category="APPLICATION")
    c.incident_service.change_priority(admin, inc.id, Priority.P1, "Payments blocked")
    c.incident_service.assign_incident(admin, inc.id, t1.id)
    return inc


def test_p1_sla_breach_escalates_to_team_lead(c):
    inc = _p1_assigned_to_t1(c)
    lead = user(c, "lead@itsm.local")
    c.clock.advance(minutes=10)   # past SVC-PAY's 3-minute P1 response deadline
    c.sla.scan()

    reloaded = c.incidents.get(inc.id)
    assert reloaded.assigned_to == lead.id
    assert reloaded.status == Status.ASSIGNED          # back to ASSIGNED; new owner must acknowledge

    # Lead can open and acknowledge
    assert c.incident_service.get_incident(lead, inc.id).id == inc.id
    c.incident_service.acknowledge(lead, inc.id)
    assert c.incidents.get(inc.id).status == Status.ACKNOWLEDGED


def test_second_scan_does_not_escalate_again(c):
    inc = _p1_assigned_to_t1(c)
    lead = user(c, "lead@itsm.local")
    c.clock.advance(minutes=10)
    c.sla.scan()

    after_first = [a.action for a in c.audit.list_for_incident(inc.id)]
    assert after_first.count("INCIDENT_REASSIGNED") == 1

    c.sla.scan()                                       # no clock advance, second scan
    after_second = [a.action for a in c.audit.list_for_incident(inc.id)]
    assert after_second.count("INCIDENT_REASSIGNED") == 1
    assert c.incidents.get(inc.id).assigned_to == lead.id


def test_audit_shows_escalated_then_reassigned(c):
    inc = _p1_assigned_to_t1(c)
    c.clock.advance(minutes=10)
    c.sla.scan()

    actions = [a.action for a in c.audit.list_for_incident(inc.id)]
    assert actions[-2:] == ["INCIDENT_ESCALATED", "INCIDENT_REASSIGNED"], actions


def test_p3_does_not_escalate(c):
    admin = user(c, "admin@itsm.local")
    t1 = user(c, "t1@itsm.local")
    inc = report(c, email="e1@itsm.local", service="SVC-DB", category="DATABASE")   # P3 by default
    c.incident_service.assign_incident(admin, inc.id, t1.id)

    c.clock.advance(minutes=600)                      # far past any P3 deadline
    c.sla.scan()

    assert c.incidents.get(inc.id).assigned_to == t1.id
    actions = [a.action for a in c.audit.list_for_incident(inc.id)]
    assert "INCIDENT_ESCALATED" not in actions


def test_no_qualified_manager_leaves_assignment_unchanged(c):
    admin = user(c, "admin@itsm.local")
    # A technician with no manager — the walk from reports_to ends immediately.
    c.admin.create_user(admin, Role.TECHNICIAN, "Orphan", "orphan@itsm.local", "password123",
                        reports_to=None, skills=["APPLICATION"], max_workload=5)
    orphan = user(c, "orphan@itsm.local")

    inc = report(c, email="e1@itsm.local", service="SVC-PAY", category="APPLICATION")
    c.incident_service.change_priority(admin, inc.id, Priority.P1, "Test")
    c.incident_service.assign_incident(admin, inc.id, orphan.id)

    c.clock.advance(minutes=10)
    c.sla.scan()

    assert c.incidents.get(inc.id).assigned_to == orphan.id


def test_unassigned_breach_notifies_assigners_not_reporter(c):
    admin = user(c, "admin@itsm.local")
    lead = user(c, "lead@itsm.local")
    mgr = user(c, "mgr@itsm.local")
    reporter = user(c, "e1@itsm.local")

    inc = report(c, email="e1@itsm.local", service="SVC-PAY", category="APPLICATION")
    c.incident_service.change_priority(admin, inc.id, Priority.P1, "Test")
    # Deliberately NOT assigned.

    c.clock.advance(minutes=10)
    c.sla.scan()

    SLA_EVENTS = (EV_SLA_VIOLATED, EV_SLA_WARNING, EV_ESCALATED)

    def _sla_notifs(uid):
        return [n for n in c.notifications.list_for_recipient(uid)
                if inc.id in (n["subject"] or "")
                and any(ev in (n["body"] or "") for ev in SLA_EVENTS)]

    # Reporter got none of the SLA/escalation noise
    assert _sla_notifs(reporter.id) == []

    # All three assigners got at least one
    for assigner in (admin, lead, mgr):
        assert len(_sla_notifs(assigner.id)) >= 1, f"{assigner.email} was not notified"
