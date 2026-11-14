import pytest
from app.domain.enums import Priority, Role
from app.domain.exceptions import (AuthenticationError, AuthorizationError, MissingSlaError, ValidationError, NotFoundError)
from tests.helpers import report, user

def test_admin_creates_technician_via_factory_and_they_can_log_in(c):
    t = c.admin.create_user(user(c, "admin@itsm.local"), Role.TECHNICIAN, "New Tech", "nt@itsm.local", "longpassword1", reports_to="U-LEAD", skills=["cloud"])
    assert t.has_skill("CLOUD") and c.auth.login("nt@itsm.local", "longpassword1").id == t.id

def test_non_technician_cannot_get_skills_and_employee_cannot_create_users(c):
    with pytest.raises(ValidationError): c.admin.create_user(user(c, "admin@itsm.local"), Role.EMPLOYEE, "X", "x@itsm.local", "longpassword1", skills=["CLOUD"])
    with pytest.raises(AuthorizationError): c.admin.create_user(user(c, "e1@itsm.local"), Role.ADMIN, "X", "x@itsm.local", "longpassword1")

def test_deactivated_user_cannot_log_in_and_admin_cannot_deactivate_self(c):
    c.admin.set_user_active(user(c, "admin@itsm.local"), "U-E2", False)
    with pytest.raises(AuthenticationError): c.auth.login("e2@itsm.local", "password123")
    with pytest.raises(ValidationError): c.admin.set_user_active(user(c, "admin@itsm.local"), "U-ADMIN", False)

def test_service_specific_sla_overrides_default_and_falls_back(c):
    from datetime import datetime, timezone, timedelta
    t0 = datetime(2026, 11, 14, 10, 0, tzinfo=timezone.utc)
    assert c.sla.deadlines_for(Priority.P1, t0, "SVC-PAY") == (t0 + timedelta(minutes=3), t0 + timedelta(minutes=20))   # override
    assert c.sla.deadlines_for(Priority.P1, t0, "SVC-DB") == (t0 + timedelta(minutes=5), t0 + timedelta(minutes=30))    # default

def test_missing_sla_blocks_creation_and_saves_nothing(c):
    c.db.execute("DELETE FROM sla_policies")
    with pytest.raises(MissingSlaError): report(c)
    assert c.incidents.list_by_reporter("U-E1") == []

def test_sla_policy_edit_validates_and_is_audited_without_changing_existing_incidents(c):
    inc = report(c); before = c.incidents.get(inc.id).sla
    with pytest.raises(ValidationError): c.admin.set_sla_policy(user(c, "admin@itsm.local"), Priority.P3, 90, 30)
    c.admin.set_sla_policy(user(c, "admin@itsm.local"), Priority.P3, 10, 60)
    assert c.incidents.get(inc.id).sla == before                       # snapshot: history is not rewritten
    assert c.audit.list_all()[0].action == "CONFIG_CHANGED"

def test_notes_stay_internal_and_info_request_reply_cycle_works(c):
    inc = report(c); c.incident_service.assign_incident(user(c, "admin@itsm.local"), inc.id, "U-T1")
    c.collab.add_note(user(c, "t1@itsm.local"), inc.id, "Checking slow query log", internal=True)
    c.collab.request_info(user(c, "t1@itsm.local"), inc.id, "Which report is slow?")
    c.collab.reply(user(c, "e1@itsm.local"), inc.id, "Monthly sales report")
    assert len(c.collab.list_comments(user(c, "t1@itsm.local"), inc.id)) == 3
    assert [x.kind for x in c.collab.list_comments(user(c, "e1@itsm.local"), inc.id)] == ["REQUEST", "REPLY"]
    with pytest.raises(AuthorizationError): c.collab.add_note(user(c, "t2@itsm.local"), inc.id, "not mine")

def test_feedback_only_after_resolution_once_and_in_range(c):
    inc = report(c); s = c.incident_service; e1 = user(c, "e1@itsm.local")
    with pytest.raises(ValidationError): c.collab.submit_feedback(e1, inc.id, 5)           # too early
    s.assign_incident(user(c, "admin@itsm.local"), inc.id, "U-T1"); t1 = user(c, "t1@itsm.local")
    s.acknowledge(t1, inc.id); s.start_investigation(t1, inc.id); s.resolve(t1, inc.id, "fixed")
    with pytest.raises(ValidationError): c.collab.submit_feedback(e1, inc.id, 9)           # out of range
    c.collab.submit_feedback(e1, inc.id, 4, "quick")
    with pytest.raises(ValidationError): c.collab.submit_feedback(e1, inc.id, 5)           # only once

def test_search_filters_status_and_category(c):   # TODO(Gaurav)
    from app.domain.filters import IncidentFilter
    from app.domain.enums import Status
    inc = report(c)
    assert [i.id for i in c.incidents.search(IncidentFilter(status=Status.CLASSIFIED, category="DATABASE"))] == [inc.id]
