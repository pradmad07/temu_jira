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

def test_admin_audit_search_and_sort(client):
    from tests.helpers import report, user
    from app.main import app
    c = app.state.container
    admin_user = user(c, "admin@itsm.local")
    # Trigger some audited actions
    c.admin.add_category(admin_user, "AUDITTESTCAT")
    inc = report(c, email="e1@itsm.local", service="SVC-DB", category="DATABASE")
    
    _login(client, email="admin@itsm.local")
    
    # Text search
    res = client.get("/admin/audit?text=AUDITTESTCAT")
    assert res.status_code == 200
    assert "Category added: AUDITTESTCAT" in res.text
    
    # Non-matching text search
    res_nomatch = client.get("/admin/audit?text=NONEXISTENT_XYZ_TERM")
    assert res_nomatch.status_code == 200
    assert "No audit records found matching your query criteria." in res_nomatch.text
    
    # Action filter
    res_act = client.get("/admin/audit?action=CONFIG_CHANGED")
    assert res_act.status_code == 200
    assert "CONFIG_CHANGED" in res_act.text
    
    # Incident ID filter
    res_inc = client.get(f"/admin/audit?incident_id={inc.id}")
    assert res_inc.status_code == 200
    assert inc.id in res_inc.text
    
    # Sort order
    res_sort_asc = client.get("/admin/audit?sort=timestamp_asc")
    assert res_sort_asc.status_code == 200
    
    res_sort_action = client.get("/admin/audit?sort_by=action&sort_dir=asc")
    assert res_sort_action.status_code == 200

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
    assert "Technician Assignment &amp; Recommendations" in res.text or "Technician Assignment & Recommendations" in res.text
    assert "/admin/incidents" in res.text
    assert "Back to All Incidents" in res.text

def test_admin_can_access_employee_incidents_without_403(client):
    _login(client, email="admin@itsm.local")
    res = client.get("/employee/incidents")
    assert res.status_code == 200

def test_admin_can_assign_technician_to_incident(client):
    from tests.helpers import report, user
    from app.main import app
    c = app.state.container
    inc = report(c, email="e1@itsm.local", service="SVC-DB", category="DATABASE")
    t1 = user(c, "t1@itsm.local")
    _login(client, email="admin@itsm.local")
    
    res = client.post(f"/admin/incidents/{inc.id}/assign", data={"technician_id": t1.id})
    assert res.status_code == 303
    
    reloaded = c.incident_service.get_incident(user(c, "admin@itsm.local"), inc.id)
    assert reloaded.assigned_to == t1.id

