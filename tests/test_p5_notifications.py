import logging
import pytest
from starlette.testclient import TestClient
from app.main import app
from app.container import build_container
from app.seed import seed
from app.domain.events import IncidentEvent, EV_ASSIGNED
from app.services.notifications import InAppChannel, NotificationService, NotificationChannel
from tests.helpers import FakeClock, report, user


@pytest.fixture
def client():
    app.state.container = build_container(":memory:", clock=FakeClock(), auto_assign=False)
    seed(app.state.container)
    return TestClient(app, follow_redirects=False)


def _login(client, email="e1@itsm.local", password="password123"):
    assert client.post("/login", data={"email": email, "password": password}).status_code == 303


# ---------- (a) ownership ----------

def test_other_user_cannot_mark_my_notification_read(client):
    c = app.state.container
    admin = user(c, "admin@itsm.local")
    t1 = user(c, "t1@itsm.local")
    inc = report(c, email="e1@itsm.local", service="SVC-DB", category="DATABASE")
    c.incident_service.assign_incident(admin, inc.id, t1.id)

    t1_notes = c.notifications.list_for_recipient(t1.id, channel="IN_APP")
    assert t1_notes, "sanity: t1 must have at least one IN_APP notification"
    target_id = t1_notes[0]["id"]

    _login(client, email="e2@itsm.local")             # someone else
    res = client.post(f"/notifications/{target_id}/read")
    assert res.status_code == 303                     # silent — no 4xx, no information leak

    reloaded = [n for n in c.notifications.list_for_recipient(t1.id, channel="IN_APP")
                if n["id"] == target_id][0]
    assert reloaded["is_read"] == 0                   # still unread


# ---------- (b) config events create no notifications ----------

def test_config_change_creates_no_notifications(c):
    admin = user(c, "admin@itsm.local")
    before = len(c.notifications.list_for_recipient(admin.id))
    c.admin.add_category(admin, "NEWCAT")              # publishes CONFIG_CHANGED (incident_id=None)
    after = len(c.notifications.list_for_recipient(admin.id))
    assert after == before, "admin must not self-notify on config changes"


# ---------- (c) one CLASSIFIED notification for the reporter ----------

def test_reporter_gets_one_classified_notification_per_report(c):
    inc = report(c, email="e1@itsm.local", service="SVC-DB", category="DATABASE")
    e1_in_app = c.notifications.list_for_recipient("U-E1", channel="IN_APP")

    classified = [n for n in e1_in_app if "Classified" in (n["subject"] or "")]
    assert len(classified) == 1, f"expected 1 CLASSIFIED notification, got {len(classified)}"

    created = [n for n in e1_in_app if "Created" in (n["subject"] or "") and inc.id in (n["subject"] or "")]
    assert created == [], "EV_CREATED must not produce a notification anymore"


# ---------- (d) bell counts IN_APP only ----------

def test_count_unread_only_counts_requested_channel(c):
    admin = user(c, "admin@itsm.local")
    t1 = user(c, "t1@itsm.local")
    inc = report(c, email="e1@itsm.local", service="SVC-DB", category="DATABASE")
    c.incident_service.assign_incident(admin, inc.id, t1.id)

    # One EV_ASSIGNED event -> exactly one IN_APP row and one EMAIL row, both unread
    assert c.notifications.count_unread(t1.id, channel="IN_APP") == 1
    assert c.notifications.count_unread(t1.id, channel="EMAIL") == 1
    # Total unread rows (both channels) is 2 — the bell deliberately ignores EMAIL
    assert len(c.notifications.list_for_recipient(t1.id, unread_only=True)) == 2


# ---------- (e) failures are logged, not swallowed ----------

def test_failed_channel_send_is_logged(c, caplog):
    class BrokenChannel(NotificationChannel):
        def send(self, recipient_id, subject, body):
            raise RuntimeError("smtp timeout simulated")

    inc = report(c, email="e1@itsm.local", service="SVC-DB", category="DATABASE")
    svc = NotificationService([BrokenChannel(), InAppChannel()], users=c.users, incidents=c.incidents)

    with caplog.at_level(logging.ERROR):
        svc.on_event(IncidentEvent(EV_ASSIGNED, inc.id, None, "CLASSIFIED", "ASSIGNED", "test"))

    errs_with_tb = [r for r in caplog.records if r.levelno >= logging.ERROR and r.exc_info]
    assert errs_with_tb, "expected logging.exception to attach a traceback"
