import pytest
from starlette.testclient import TestClient
from app.main import app
from app.domain.enums import Status
from app.domain.events import EV_REJECTED
from app.container import build_container
from app.seed import seed
from tests.helpers import FakeClock, report, user

@pytest.fixture
def client():
    app.state.container = build_container(":memory:", clock=FakeClock(), auto_assign=False)
    seed(app.state.container)
    return TestClient(app, follow_redirects=False)

def _login(client, email="e1@itsm.local", password="password123"):
    res = client.post("/login", data={"email": email, "password": password})
    assert res.status_code == 303

def _to_verified(c):
    admin = user(c, "admin@itsm.local"); t1 = user(c, "t1@itsm.local"); e1 = user(c, "e1@itsm.local")
    inc = report(c, email="e1@itsm.local", service="SVC-DB", category="DATABASE")
    c.incident_service.assign_incident(admin, inc.id, t1.id)
    c.incident_service.acknowledge(t1, inc.id)
    c.incident_service.start_investigation(t1, inc.id)
    c.incident_service.resolve(t1, inc.id, "Fixed")
    c.incident_service.verify(e1, inc.id)
    return inc

def test_reporter_can_close_verified_incident(client):
    c = app.state.container
    inc = _to_verified(c)
    _login(client, email="e1@itsm.local")
    res = client.post(f"/employee/incidents/{inc.id}/close")
    assert res.status_code == 303
    assert "msg=" in res.headers["location"]
    reloaded = c.incidents.get(inc.id)
    assert reloaded.status == Status.CLOSED
    assert reloaded.closed_at is not None

def test_other_employee_cannot_close(client):
    c = app.state.container
    inc = _to_verified(c)
    _login(client, email="e2@itsm.local")
    res = client.post(f"/employee/incidents/{inc.id}/close")
    assert res.status_code == 303
    assert "error=" in res.headers["location"]
    assert c.incidents.get(inc.id).status == Status.VERIFIED

def test_closing_resolved_incident_shows_error_and_changes_nothing(client):
    c = app.state.container
    admin = user(c, "admin@itsm.local"); t1 = user(c, "t1@itsm.local")
    inc = report(c, email="e1@itsm.local", service="SVC-DB", category="DATABASE")
    c.incident_service.assign_incident(admin, inc.id, t1.id)
    c.incident_service.acknowledge(t1, inc.id)
    c.incident_service.start_investigation(t1, inc.id)
    c.incident_service.resolve(t1, inc.id, "Fixed")   # still RESOLVED, not VERIFIED

    _login(client, email="e1@itsm.local")
    res = client.post(f"/employee/incidents/{inc.id}/close")
    assert res.status_code == 303
    assert "error=" in res.headers["location"]
    assert c.incidents.get(inc.id).status == Status.RESOLVED

def test_admin_can_close_verified_incident(client):
    c = app.state.container
    inc = _to_verified(c)
    _login(client, email="admin@itsm.local")
    res = client.post(f"/admin/incidents/{inc.id}/close")
    assert res.status_code == 303
    assert c.incidents.get(inc.id).status == Status.CLOSED

def test_close_button_absent_unless_verified(client):
    c = app.state.container
    admin = user(c, "admin@itsm.local"); t1 = user(c, "t1@itsm.local")
    inc = report(c, email="e1@itsm.local", service="SVC-DB", category="DATABASE")
    c.incident_service.assign_incident(admin, inc.id, t1.id)
    c.incident_service.acknowledge(t1, inc.id)
    c.incident_service.start_investigation(t1, inc.id)
    c.incident_service.resolve(t1, inc.id, "Fixed")   # RESOLVED

    _login(client, email="e1@itsm.local")
    res = client.get(f"/employee/incidents/{inc.id}")
    assert res.status_code == 200
    assert "Close Incident" not in res.text

def test_reject_keeps_comment_and_publishes_one_event(client):
    c = app.state.container
    admin = user(c, "admin@itsm.local"); t1 = user(c, "t1@itsm.local")
    inc = report(c, email="e1@itsm.local", service="SVC-DB", category="DATABASE")
    c.incident_service.assign_incident(admin, inc.id, t1.id)
    c.incident_service.acknowledge(t1, inc.id)
    c.incident_service.start_investigation(t1, inc.id)
    c.incident_service.resolve(t1, inc.id, "Fixed")

    events = []
    c.bus.subscribe(lambda e: events.append(e))

    _login(client, email="e1@itsm.local")
    res = client.post(f"/employee/incidents/{inc.id}/reject",
                      data={"reason": "Checkout 500 still happening"})
    assert res.status_code == 303

    comments = c.collab.list_comments(t1, inc.id)
    assert any("Checkout 500 still happening" in com.body for com in comments)
    assert any(com.kind == "REPLY" for com in comments)

    # The invariant P1 protects: one reject = exactly one EV_REJECTED event, no side events.
    # (The notifications table gains +2 rows because both channels write to it — that is
    #  the separate §7 "noise" bug, tracked for a later task.)
    assert [e.type for e in events] == [EV_REJECTED], [e.type for e in events]

    t1_notes = c.notifications.list_for_recipient(t1.id)
    assert any("Checkout 500 still happening" in n["body"] for n in t1_notes)
