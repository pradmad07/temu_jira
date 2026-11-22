"""OBSERVER + ADAPTER (owner: Gaurav). One event -> every channel. Add a channel = add a class."""
import logging
from abc import ABC, abstractmethod
from collections import deque
from typing import Optional
from app.domain.events import (
    IncidentEvent, EV_CREATED, EV_CLASSIFIED, EV_ASSIGNED, EV_ACKNOWLEDGED,
    EV_STARTED, EV_RESOLVED, EV_VERIFIED, EV_REJECTED, EV_CLOSED,
    EV_SLA_WARNING, EV_SLA_VIOLATED, EV_ESCALATED, EV_REASSIGNED,
    EV_PRIORITY_CHANGED, EV_NOTE_ADDED, EV_INFO_REQUESTED, EV_INFO_PROVIDED,
    EV_FEEDBACK
)
from app.domain.permissions import Perm

class NotificationChannel(ABC):
    def __init__(self, repo=None):
        self.sent: deque = deque(maxlen=500)    # bounded in-memory log; len() and [i] still work
        self._repo = repo

    @abstractmethod
    def send(self, recipient_id: str, subject: str, body: str) -> None: ...

class InAppChannel(NotificationChannel):
    """In-app alert delivered to user notifications table and in-memory delivery log."""
    def __init__(self, repo=None):
        super().__init__(repo)

    def send(self, recipient_id: str, subject: str, body: str) -> None:
        record = {
            "recipient_id": recipient_id,
            "channel": "IN_APP",
            "subject": subject,
            "body": body,
        }
        self.sent.append(record)
        if self._repo:
            self._repo.add(recipient_id, "IN_APP", subject, body, status="DELIVERED")

class SimulatedEmailChannel(NotificationChannel):
    """Simulated external SMTP channel, clearly labeled for audit & course rubric."""
    def __init__(self, repo=None):
        super().__init__(repo)

    def send(self, recipient_id: str, subject: str, body: str) -> None:
        labeled_subject = f"[SIMULATED EMAIL] {subject}"
        labeled_body = (
            f"--- [SIMULATED EMAIL NOTIFICATION] ---\n"
            f"To: {recipient_id}\n"
            f"Subject: {subject}\n\n"
            f"{body}\n"
            f"--------------------------------------"
        )
        record = {
            "recipient_id": recipient_id,
            "channel": "SIMULATED_EMAIL",
            "subject": labeled_subject,
            "body": labeled_body,
        }
        self.sent.append(record)
        if self._repo:
            self._repo.add(recipient_id, "EMAIL", labeled_subject, labeled_body, status="SENT")

class NotificationService:
    def __init__(self, channels: list[NotificationChannel], users=None, incidents=None):
        self._channels = channels
        self._users = users
        self._incidents = incidents

    def on_event(self, event: IncidentEvent) -> None:
        recipients = self._resolve_recipients(event)
        subject, body = self._build_message(event)
        for recipient_id in recipients:
            for channel in self._channels:
                try:
                    channel.send(recipient_id, subject, body)
                except Exception:
                    logging.exception(
                        "Notification channel %s failed for recipient %s on event %s",
                        type(channel).__name__, recipient_id, event.type,
                    )

    def _resolve_recipients(self, event: IncidentEvent) -> set[str]:
        recipients: set[str] = set()
        inc = None
        if self._incidents and event.incident_id:
            try:
                inc = self._incidents.get(event.incident_id)
            except Exception:
                inc = None

        if inc:
            reporter_id = inc.reporter_id
            assignee_id = inc.assigned_to

            # (c) Only CLASSIFIED carries the "priority + deadline" summary.
            # EV_CREATED is intentionally omitted — the reporter already knows they just reported it.
            if event.type == EV_CLASSIFIED:
                if reporter_id:
                    recipients.add(reporter_id)

            elif event.type in (EV_ASSIGNED, EV_REASSIGNED):
                if assignee_id:
                    recipients.add(assignee_id)
                if getattr(event, "previous_assignee", None):
                    recipients.add(event.previous_assignee)
                elif reporter_id:
                    recipients.add(reporter_id)

            elif event.type in (EV_ACKNOWLEDGED, EV_STARTED, EV_RESOLVED):
                if reporter_id:
                    recipients.add(reporter_id)

            elif event.type in (EV_VERIFIED, EV_REJECTED):
                if assignee_id:
                    recipients.add(assignee_id)

            elif event.type == EV_CLOSED:
                if reporter_id:
                    recipients.add(reporter_id)
                if assignee_id:
                    recipients.add(assignee_id)

            elif event.type in (EV_SLA_WARNING, EV_SLA_VIOLATED, EV_ESCALATED):
                if assignee_id:
                    if event.type == EV_ESCALATED and self._users:
                        user_obj = self._users.get(assignee_id)
                        if user_obj and user_obj.reports_to:
                            recipients.add(user_obj.reports_to)
                    recipients.add(assignee_id)
                elif self._users:
                    for u in self._users.list_all():
                        if u.active and u.can(Perm.INCIDENT_ASSIGN):
                            recipients.add(u.id)

            elif event.type == EV_INFO_REQUESTED:
                if reporter_id:
                    recipients.add(reporter_id)

            elif event.type == EV_INFO_PROVIDED:
                if assignee_id:
                    recipients.add(assignee_id)

            elif event.type == EV_NOTE_ADDED:
                if assignee_id:
                    recipients.add(assignee_id)

            elif event.type == EV_FEEDBACK:
                if assignee_id:
                    recipients.add(assignee_id)

        # (b) Events with no incident (CONFIG_CHANGED, USER_CHANGED) are audit-only.
        # The previous fallback "add the actor" turned admin actions into self-notifications.

        return recipients

    def _build_message(self, event: IncidentEvent) -> tuple[str, str]:
        prefix = f"[{event.incident_id}]" if event.incident_id else "[ITSM]"
        type_title = event.type.replace("INCIDENT_", "").replace("_", " ").title()
        subject = f"{prefix} {type_title}: {event.description[:50]}"
        body = (
            f"Event: {event.type}\n"
            f"Incident: {event.incident_id or 'N/A'}\n"
            f"Status: {event.old_status or '-'} -> {event.new_status or '-'}\n"
            f"Details: {event.description}\n"
        )
        return subject, body
