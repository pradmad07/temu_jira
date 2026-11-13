from datetime import timedelta
from app.domain.enums import Category, Status
from tests.helpers import make_incident

def _report(c):
    return c.incident_service.create_incident(c.users.get_by_email("e1@itsm.local"), "Pay down", "Cannot pay", Category.APPLICATION, "SVC-PAY", 5, 5, 10)

def test_created_at_and_audit_time_come_from_the_injected_clock(c):
    c.clock.advance(minutes=90)
    inc = _report(c)
    assert inc.created_at == c.clock.now()
    assert c.audit.list_for_incident(inc.id)[0].timestamp == c.clock.now()

def test_ack_and_resolve_times_survive_save_and_reload(c):
    i = make_incident(); i.classify(); i.assign("U-T1")
    t1, t2 = c.clock.now(), c.clock.now() + timedelta(minutes=7)
    i.acknowledge(at=t1); i.start(); i.resolve("fixed", at=t2); c.incidents.save(i)
    back = c.incidents.get(i.id)
    assert back.acknowledged_at == t1 and back.resolved_at == t2

def test_rejected_resolution_clears_resolved_time():
    i = make_incident(); i.classify(); i.assign("U-T1"); i.acknowledge(); i.start(); i.resolve("x"); i.reject()
    assert i.resolved_at is None

def test_violation_is_recorded_only_once(c):
    t = c.clock.now()
    assert c.violations.record("INC1", "RESPONSE_VIOLATION", t) is True
    assert c.violations.record("INC1", "RESPONSE_VIOLATION", t) is False
    assert len(c.violations.list_for_incident("INC1")) == 1

def test_list_unresolved_excludes_closed_incidents(c):
    open_inc = _report(c)
    done = make_incident(); done.classify(); done.assign("U-T1"); done.acknowledge(); done.start(); done.resolve("ok"); done.verify(); done.close()
    c.incidents.save(done)
    ids = [i.id for i in c.incidents.list_unresolved()]
    assert open_inc.id in ids and done.id not in ids and done.status == Status.CLOSED
