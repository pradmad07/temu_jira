import re
import pytest
from starlette.testclient import TestClient
from app.main import app
from app.container import build_container
from app.seed import seed
from tests.helpers import FakeClock, report, user

@pytest.fixture
def client():
    app.state.container = build_container(":memory:", clock=FakeClock(), auto_assign=False)
    seed(app.state.container)
    return TestClient(app, follow_redirects=False)

def _login(client, email, password="password123"):
    res = client.post("/login", data={"email": email, "password": password})
    assert res.status_code == 303

def test_technician_home_shows_workload_with_limit(client):
    c = app.state.container
    t1 = user(c, "t1@itsm.local")
    _login(client, email="t1@itsm.local")
    res = client.get("/technician")
    assert res.status_code == 200
    # technician form: "<active>/<max_workload>"
    assert re.search(r"Active workload:\s*<b>\d+/\d+</b>", res.text), res.text
    assert "/None" not in res.text
    assert "None</b>" not in res.text
    # and the limit is really their own
    assert re.search(rf"Active workload:\s*<b>\d+/{t1.max_workload}</b>", res.text)

def test_team_lead_home_does_not_crash_and_has_no_limit(client):
    _login(client, email="lead@itsm.local")
    res = client.get("/technician")
    assert res.status_code == 200
    assert "Active workload" in res.text
    # team lead form: plain "<active>" — no "/<limit>", no "None"
    assert re.search(r"Active workload:\s*<b>\d+</b>", res.text), res.text
    assert "/None" not in res.text
    assert "None</b>" not in res.text

def test_team_lead_can_open_incident_assigned_to_them(client):
    c = app.state.container
    lead = user(c, "lead@itsm.local")
    inc = report(c, email="e1@itsm.local", service="SVC-DB", category="DATABASE")

    # We can't use IncidentService.assign_incident here — a team lead lacks INCIDENT_WORK,
    # so the service refuses them (correct). We're testing VIEW permission, not assignment.
    # So drive the state machine directly, the same way _assign does internally:
    # `Incident.assign(technician_id=...)` is the State-pattern entry point.
    inc.assign(technician_id=lead.id)   # CLASSIFIED -> ASSIGNED, sets assigned_to
    c.incidents.save(inc)               # the service normally saves after _apply

    _login(client, email="lead@itsm.local")
    res = client.get(f"/technician/incidents/{inc.id}")
    assert res.status_code == 200
    assert inc.id in res.text
    assert inc.title in res.text
