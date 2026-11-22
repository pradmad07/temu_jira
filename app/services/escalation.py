"""OBSERVER: on escalation, reassign an unacknowledged P1 to the first manager up the chain
who can work incidents. Subscribed to EV_ESCALATED; the reassignment itself goes through
IncidentService._assign so state rules, audit and EV_REASSIGNED notifications all apply."""
import logging
from app.domain.events import EV_ESCALATED


class Escalator:
    def __init__(self, incident_service):
        self._svc = incident_service

    def on_event(self, e):
        if e.type != EV_ESCALATED:
            return
        try:
            self._svc.escalate(e.incident_id)
        except Exception as ex:                      # never let one bad escalation crash the scan
            logging.warning("Escalation of %s failed: %s", e.incident_id, ex)
