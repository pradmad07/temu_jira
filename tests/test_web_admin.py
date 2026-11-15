import pytest
from starlette.testclient import TestClient
from app.main import app

from app.container import build_container
from app.seed import seed
from tests.helpers import FakeClock

@pytest.fixture
def client():
    app.state.container = build_container(":memory:", clock=FakeClock(), auto_assign=False)
    seed(app.state.container)
    return TestClient(app, follow_redirects=False)

def _login(client, email="admin@itsm.local", password="password123"):
    res = client.post("/login", data={"email": email, "password": password})
    assert res.status_code == 303
    return res

def test_unauthenticated_access_to_admin_redirects_to_login(client):
    res = client.get("/admin")
    assert res.status_code == 303
    assert "/login" in res.headers["location"]

def test_employee_forbidden_from_admin_dashboard(client):
    _login(client, email="e1@itsm.local")
    res = client.get("/admin")
    assert res.status_code == 403

def test_admin_can_access_dashboard(client):
    _login(client, email="admin@itsm.local")
    res = client.get("/admin")
    assert res.status_code == 200
    assert "ITSM Executive Dashboard" in res.text
    assert "Total Incidents" in res.text

def test_admin_can_trigger_sla_scan(client):
    _login(client, email="admin@itsm.local")
    res = client.post("/admin/sla/scan")
    assert res.status_code == 303
    assert "/admin" in res.headers["location"]

def test_admin_can_update_assignment_strategy(client):
    _login(client, email="admin@itsm.local")
    res = client.post("/admin/strategy", data={"strategy": "load"})
    assert res.status_code == 303
    assert "/admin" in res.headers["location"]

def test_admin_can_view_incidents_list_and_filter(client):
    _login(client, email="admin@itsm.local")
    res = client.get("/admin/incidents?status=CLASSIFIED")
    assert res.status_code == 200
    assert "Incident Operations Center" in res.text

def test_admin_can_view_and_manage_users(client):
    _login(client, email="admin@itsm.local")
    res = client.get("/admin/users")
    assert res.status_code == 200
    assert "User &amp; Technician Management" in res.text or "User & Technician Management" in res.text
    assert "admin@itsm.local" in res.text

def test_admin_can_view_services_and_sla(client):
    _login(client, email="admin@itsm.local")
    res = client.get("/admin/services")
    assert res.status_code == 200
    assert "Business Services" in res.text
    assert "SLA Policy Configuration Matrix" in res.text

def test_admin_can_view_audit_trail(client):
    _login(client, email="admin@itsm.local")
    res = client.get("/admin/audit")
    assert res.status_code == 200
    assert "System Audit Trail Log" in res.text

def test_admin_can_inspect_incident_detail(client):
    from tests.helpers import report
    from app.main import app
    c = app.state.container
    inc = report(c, email="e1@itsm.local", service="SVC-DB", category="DATABASE")
    _login(client, email="admin@itsm.local")
    res = client.get(f"/admin/incidents/{inc.id}")
    assert res.status_code == 200
    assert inc.id in res.text
    assert inc.title in res.text
