import pytest
from starlette.testclient import TestClient
from app.main import app
from app.container import build_container
from app.seed import seed
from app.domain.enums import Category
from app.domain.exceptions import ValidationError
from tests.helpers import FakeClock, user


@pytest.fixture
def client():
    app.state.container = build_container(":memory:", clock=FakeClock(), auto_assign=False)
    seed(app.state.container)
    return TestClient(app, follow_redirects=False)


def _login(client, email="e1@itsm.local", password="password123"):
    assert client.post("/login", data={"email": email, "password": password}).status_code == 303


# ---------- (b) description length ----------

def test_19_char_description_rejected(c):
    with pytest.raises(ValidationError, match="at least 20 characters"):
        c.incident_service.create_incident(
            user(c, "e1@itsm.local"), "Payment fails", "x" * 19,
            Category.DATABASE, "SVC-DB", 3, 3)


def test_20_char_description_accepted(c):
    inc = c.incident_service.create_incident(
        user(c, "e1@itsm.local"), "Payment fails", "x" * 20,
        Category.DATABASE, "SVC-DB", 3, 3)
    assert inc.description == "x" * 20


def test_whitespace_padding_does_not_count(c):
    with pytest.raises(ValidationError, match="at least 20 characters"):
        c.incident_service.create_incident(
            user(c, "e1@itsm.local"), "Payment fails",
            "     " + "x" * 15 + "     ",
            Category.DATABASE, "SVC-DB", 3, 3)


def test_web_form_rejects_short_description(client):
    _login(client, email="e1@itsm.local")
    res = client.post("/employee/incidents/new", data={
        "title": "Payment fails via web",
        "description": "short desc",
        "category": "DATABASE",
        "service_id": "SVC-DB",
        "impact": 3,
        "urgency": 3,
        "affected_users": 1,
    })
    # main.py turns ItsmError into a 4xx response containing the message
    assert res.status_code >= 400
    assert "at least 20 characters" in res.text
    # Nothing was persisted
    e1 = user(app.state.container, "e1@itsm.local")
    assert all(i.title != "Payment fails via web"
               for i in app.state.container.incidents.list_by_reporter(e1.id))


# ---------- (a) confirm password ----------

def test_register_with_matching_passwords_succeeds(client):
    res = client.post("/register", data={
        "name": "New User", "email": "new@itsm.local",
        "password": "password123", "confirm_password": "password123",
    })
    assert res.status_code == 303
    assert app.state.container.users.get_by_email("new@itsm.local") is not None


def test_register_with_mismatched_passwords_shows_error(client):
    res = client.post("/register", data={
        "name": "New User", "email": "new@itsm.local",
        "password": "password123", "confirm_password": "different",
    })
    assert res.status_code == 400
    assert "Passwords do not match" in res.text
    assert app.state.container.users.get_by_email("new@itsm.local") is None


def test_admin_create_user_with_mismatched_passwords_creates_nothing(client):
    _login(client, email="admin@itsm.local")
    res = client.post("/admin/users/new", data={
        "name": "New Tech", "email": "newtech@itsm.local",
        "password": "password123", "confirm_password": "different",
        "role": "TECHNICIAN", "skills": "DATABASE", "max_workload": 5,
    })
    assert res.status_code == 303
    assert "error=" in res.headers["location"]
    assert app.state.container.users.get_by_email("newtech@itsm.local") is None
