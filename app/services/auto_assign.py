"""OBSERVER: when an incident is classified, assign it using the admin-selected strategy.
It is a subscriber, so removing it (container auto_assign=False) changes no other class."""
import logging
from app.domain.events import EV_CLASSIFIED
from app.domain.exceptions import TechnicianUnavailableError

class AutoAssigner:
    def __init__(self, incident_service): self._svc = incident_service
    def on_event(self, e):
        if e.type != EV_CLASSIFIED: return
        try: self._svc.auto_assign(e.incident_id)
        except TechnicianUnavailableError as ex: logging.info("Left %s unassigned: %s", e.incident_id, ex)   # a human assigns it
        except NotImplementedError: logging.warning("Assignment strategy not implemented yet; %s left unassigned", e.incident_id)
