import pytest
from app.domain.enums import Priority, Status
from app.domain.exceptions import AuthorizationError, InvalidTransitionError, ValidationError, WorkloadExceededError
from tests.helpers import report, user

def _to_in_progress(c):
    inc = report(c); c.incident_service.assign_incident(user(c, "admin@itsm.local"), inc.id, "U-T1")
    c.incident_service.acknowledge(user(c, "t1@itsm.local"), inc.id); c.incident_service.start_investigation(user(c, "t1@itsm.local"), inc.id)
    return inc

def test_full_workflow_through_the_service_is_audited_in_order(c):
    inc = _to_in_progress(c); s = c.incident_service
    s.resolve(user(c, "t1@itsm.local"), inc.id, "Rebuilt index"); s.verify(user(c, "e1@itsm.local"), inc.id); s.close(user(c, "e1@itsm.local"), inc.id)
    done = c.incidents.get(inc.id)
    assert done.status == Status.CLOSED and done.closed_at == c.clock.now() and done.resolution == "Rebuilt index"
    assert [a.action for a in c.audit.list_for_incident(inc.id)] == ["INCIDENT_CREATED", "INCIDENT_CLASSIFIED", "INCIDENT_ASSIGNED",
        "INCIDENT_ACKNOWLEDGED", "INVESTIGATION_STARTED", "INCIDENT_RESOLVED", "RESOLUTION_VERIFIED", "INCIDENT_CLOSED"]

def test_close_before_verification_is_rejected(c):
    inc = _to_in_progress(c)
    with pytest.raises(InvalidTransitionError): c.incident_service.close(user(c, "e1@itsm.local"), inc.id)

def test_wrong_people_are_refused(c):
    inc = _to_in_progress(c)
    with pytest.raises(AuthorizationError): c.incident_service.resolve(user(c, "t2@itsm.local"), inc.id, "x")        # not the assignee
    c.incident_service.resolve(user(c, "t1@itsm.local"), inc.id, "fixed")
    with pytest.raises(AuthorizationError): c.incident_service.verify(user(c, "e2@itsm.local"), inc.id)              # not the reporter

def test_rejected_resolution_reopens_work_and_needs_a_reason(c):
    inc = _to_in_progress(c); c.incident_service.resolve(user(c, "t1@itsm.local"), inc.id, "fixed")
    with pytest.raises(ValidationError): c.incident_service.reject_resolution(user(c, "e1@itsm.local"), inc.id, " ")
    c.incident_service.reject_resolution(user(c, "e1@itsm.local"), inc.id, "still slow")
    assert c.incidents.get(inc.id).status == Status.IN_PROGRESS and c.incidents.get(inc.id).resolved_at is None

def test_reassignment_resets_to_assigned_but_keeps_first_response_time(c):
    inc = _to_in_progress(c)
    c.incident_service.assign_incident(user(c, "admin@itsm.local"), inc.id, "U-T3")
    now = c.incidents.get(inc.id)
    assert now.status == Status.ASSIGNED and now.assigned_to == "U-T3" and now.acknowledged_at is not None
    with pytest.raises(AuthorizationError): c.incident_service.resolve(user(c, "t1@itsm.local"), inc.id, "x")        # no longer theirs

def test_workload_limit_blocks_manual_assignment(c):
    for _ in range(3): c.incident_service.assign_incident(user(c, "admin@itsm.local"), report(c).id, "U-T2")   # Tom's limit is 3
    with pytest.raises(WorkloadExceededError): c.incident_service.assign_incident(user(c, "admin@itsm.local"), report(c).id, "U-T2")

def test_change_priority_recomputes_sla_and_is_staff_only(c):
    inc = report(c)                                                  # FixedPriority -> P3
    with pytest.raises(AuthorizationError): c.incident_service.change_priority(user(c, "e1@itsm.local"), inc.id, Priority.P1, "urgent")
    c.incident_service.change_priority(user(c, "admin@itsm.local"), inc.id, Priority.P1, "Payments blocked")
    back = c.incidents.get(inc.id)
    assert back.priority == Priority.P1 and back.sla.resolution_due == back.created_at + __import__("datetime").timedelta(minutes=30)
    assert c.audit.list_for_incident(inc.id)[-1].action == "PRIORITY_CHANGED"

def test_technician_lists_only_their_incidents(c):
    mine, other = report(c), report(c)
    c.incident_service.assign_incident(user(c, "admin@itsm.local"), mine.id, "U-T1"); c.incident_service.assign_incident(user(c, "admin@itsm.local"), other.id, "U-T3")
    assert [i.id for i in c.incident_service.list_for(user(c, "t1@itsm.local"))] == [mine.id]
