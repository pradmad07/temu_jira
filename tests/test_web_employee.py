import pytest
from starlette.testclient import TestClient
from app.main import app
from tests.helpers import report, user

from app.container import build_container
from app.seed import seed
from tests.helpers import FakeClock

@pytest.fixture
def client():
    app.state.container = build_container(":memory:", clock=FakeClock(), auto_assign=False)
    seed(app.state.container)
    return TestClient(app, follow_redirects=False)

def _login(client, email="e1@itsm.local", password="password123"):
    res = client.post("/login", data={"email": email, "password": password})
    assert res.status_code == 303
    return res

def test_employee_can_view_incident_detail(client):
    c = app.state.container
    inc = report(c, email="e1@itsm.local", service="SVC-DB", category="DATABASE")
    _login(client, email="e1@itsm.local")
    res = client.get(f"/employee/incidents/{inc.id}")
    assert res.status_code == 200
    assert inc.id in res.text
    assert inc.title in res.text

def test_employee_can_reply_to_technician_info_request(client):
    c = app.state.container
    admin = user(c, "admin@itsm.local")
    t1 = user(c, "t1@itsm.local")
    inc = report(c, email="e1@itsm.local", service="SVC-DB", category="DATABASE")
    
    # Assign and acknowledge
    c.incident_service.assign_incident(admin, inc.id, t1.id)
    c.incident_service.acknowledge(t1, inc.id)
    c.incident_service.start_investigation(t1, inc.id)
    
    # Technician asks for information
    c.collab.request_info(t1, inc.id, "Which database server is down?")
    
    # Employee logs in and views ticket
    _login(client, email="e1@itsm.local")
    res = client.get(f"/employee/incidents/{inc.id}")
    assert res.status_code == 200
    assert "Which database server is down?" in res.text
    assert "Technician Question" in res.text

    # Employee submits reply
    reply_res = client.post(
        f"/employee/incidents/{inc.id}/reply",
        data={"answer": "It is db-cluster-02 in us-east region"}
    )
    assert reply_res.status_code == 303
    assert f"/employee/incidents/{inc.id}" in reply_res.headers["location"]

    # Verify reply is displayed on the page
    res_after = client.get(f"/employee/incidents/{inc.id}")
    assert res_after.status_code == 200
    assert "It is db-cluster-02 in us-east region" in res_after.text
    assert "Reporter Reply" in res_after.text

def test_employee_can_verify_and_submit_feedback(client):
    c = app.state.container
    admin = user(c, "admin@itsm.local")
    t1 = user(c, "t1@itsm.local")
    inc = report(c, email="e1@itsm.local", service="SVC-DB", category="DATABASE")
    c.incident_service.assign_incident(admin, inc.id, t1.id)
    c.incident_service.acknowledge(t1, inc.id)
    c.incident_service.start_investigation(t1, inc.id)
    c.incident_service.resolve(t1, inc.id, "Restarted replication service")

    # Employee logs in
    _login(client, email="e1@itsm.local")
    res = client.get(f"/employee/incidents/{inc.id}")
    assert res.status_code == 200
    assert "Confirm Fix (Verify)" in res.text

    # Verify resolution
    ver_res = client.post(f"/employee/incidents/{inc.id}/verify")
    assert ver_res.status_code == 303

    # Feedback form
    fb_res = client.post(
        f"/employee/incidents/{inc.id}/feedback",
        data={"rating": 5, "comment": "Fast and helpful resolution!"}
    )
    assert fb_res.status_code == 303

    # Check that feedback is displayed
    res_final = client.get(f"/employee/incidents/{inc.id}")
    assert res_final.status_code == 200
    assert "5 / 5" in res_final.text
    assert "Fast and helpful resolution!" in res_final.text

def test_employee_can_reject_resolution(client):
    c = app.state.container
    admin = user(c, "admin@itsm.local")
    t1 = user(c, "t1@itsm.local")
    inc = report(c, email="e1@itsm.local", service="SVC-DB", category="DATABASE")
    c.incident_service.assign_incident(admin, inc.id, t1.id)
    c.incident_service.acknowledge(t1, inc.id)
    c.incident_service.start_investigation(t1, inc.id)
    c.incident_service.resolve(t1, inc.id, "Flushed caches")

    _login(client, email="e1@itsm.local")
    rej_res = client.post(
        f"/employee/incidents/{inc.id}/reject",
        data={"reason": "Error 500 still occurring on checkout page"}
    )
    assert rej_res.status_code == 303

    reloaded = c.incident_service.get_incident(t1, inc.id)
    from app.domain.enums import Status
    assert reloaded.status == Status.IN_PROGRESS
