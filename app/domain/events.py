"""OBSERVER PATTERN (owner: Kevalin). Services publish events; audit + notifications subscribe independently."""
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, Optional
from .models import utcnow

EV_CREATED = "INCIDENT_CREATED"; EV_CLASSIFIED = "INCIDENT_CLASSIFIED"; EV_ASSIGNED = "INCIDENT_ASSIGNED"
EV_ACKNOWLEDGED = "INCIDENT_ACKNOWLEDGED"; EV_STARTED = "INVESTIGATION_STARTED"; EV_RESOLVED = "INCIDENT_RESOLVED"
EV_VERIFIED = "RESOLUTION_VERIFIED"; EV_REJECTED = "RESOLUTION_REJECTED"; EV_CLOSED = "INCIDENT_CLOSED"
EV_SLA_WARNING = "SLA_WARNING"; EV_SLA_VIOLATED = "SLA_VIOLATED"; EV_ESCALATED = "INCIDENT_ESCALATED"
EV_REASSIGNED = "INCIDENT_REASSIGNED"; EV_PRIORITY_CHANGED = "PRIORITY_CHANGED"; EV_NOTE_ADDED = "NOTE_ADDED"
EV_INFO_REQUESTED = "INFO_REQUESTED"; EV_INFO_PROVIDED = "INFO_PROVIDED"; EV_FEEDBACK = "FEEDBACK_SUBMITTED"
EV_CONFIG_CHANGED = "CONFIG_CHANGED"; EV_USER_CHANGED = "USER_CHANGED"   # admin actions: incident_id is None

@dataclass
class IncidentEvent:
    type: str
    incident_id: Optional[str]   # None for admin/config events
    actor_id: Optional[str]
    old_status: Optional[str]
    new_status: Optional[str]
    description: str
    timestamp: datetime = field(default_factory=utcnow)

class EventBus:
    def __init__(self): self._subscribers: list[Callable[[IncidentEvent], None]] = []
    def subscribe(self, handler): self._subscribers.append(handler)
    def publish(self, event: IncidentEvent):
        for handler in self._subscribers:
            try: handler(event)
            except Exception:  # one broken observer must never break the others
                logging.exception("Observer failed for %s", event.type)
