import pytest
from app.domain.events import (
    IncidentEvent, EV_ASSIGNED, EV_CREATED, EV_RESOLVED, EV_SLA_VIOLATED
)
from app.domain.enums import Priority
from app.services.notifications import NotificationService, InAppChannel, SimulatedEmailChannel, NotificationChannel
from tests.helpers import report, user

def test_one_event_reaches_two_channels():
    inapp, email = InAppChannel(), SimulatedEmailChannel()
    NotificationService([inapp, email]).on_event(
        IncidentEvent(EV_ASSIGNED, "INC1", "U-ADMIN", "CLASSIFIED", "ASSIGNED", "Assigned to Tina")
    )
    assert len(inapp.sent) == 1 and len(email.sent) == 1

def test_simulated_email_is_clearly_labeled():
    email = SimulatedEmailChannel()
    email.send("user@itsm.local", "Ticket Update", "Work has started on your ticket.")
    assert len(email.sent) == 1
    sent_msg = email.sent[0]
    assert "[SIMULATED EMAIL]" in sent_msg["subject"]
    assert "SIMULATED EMAIL NOTIFICATION" in sent_msg["body"]
    assert "user@itsm.local" in sent_msg["recipient_id"]

def test_notifications_persisted_to_database_on_container_event(c):
    # Reporting an incident publishes EV_CREATED and EV_CLASSIFIED through container.bus
    inc = report(c, email="e1@itsm.local", service="SVC-DB", category="DATABASE")

    # In-app and Email notifications should be saved to database
    in_app_notifs = c.notifications.list_for_recipient("U-E1")
    assert len(in_app_notifs) >= 1
    assert any(n["channel"] == "IN_APP" for n in in_app_notifs)
    assert any(inc.id in n["subject"] for n in in_app_notifs)

def test_technician_notified_on_assignment(c):
    inc = report(c, email="e1@itsm.local", service="SVC-PAY", category="APPLICATION")
    admin = user(c, "admin@itsm.local")

    # Assign to technician U-T1
    c.incident_service.assign_incident(admin, inc.id, "U-T1")

    # Check that technician received notification
    tech_notifs = c.notifications.list_for_recipient("U-T1")
    assert len(tech_notifs) >= 1
    assert any(inc.id in n["subject"] for n in tech_notifs)

def test_failing_channel_does_not_break_other_channels():
    class BrokenChannel(NotificationChannel):
        def send(self, recipient_id, subject, body):
            raise RuntimeError("Network down or SMTP connection timeout")

    broken = BrokenChannel()
    working = InAppChannel()

    # Observer resilience: broken channel failure must not block working channel
    service = NotificationService([broken, working])
    service.on_event(
        IncidentEvent(EV_CREATED, "INC99", "U-E1", None, "NEW", "System reboot issue")
    )

    assert len(working.sent) == 1
    assert len(broken.sent) == 0
