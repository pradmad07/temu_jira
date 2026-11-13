"""SLA engine. deadlines_for() is done (Kevalin); scan() and warnings are Gaurav's.
Clock is injectable so tests/demos never wait real minutes."""
from datetime import timedelta
from app.domain.clock import Clock   # re-exported: `from ...sla_service import Clock` still works
from app.domain.exceptions import MissingSlaError
from app.domain.models import SlaDeadlines

class SlaService:
    def __init__(self, policies, incidents, bus, clock: Clock, violations):
        self._policies, self._incidents, self._bus, self._clock = policies, incidents, bus, clock
        self._violations = violations   # SlaViolationRepository: record() returns True only the first time

    def deadlines_for(self, priority, created_at, service_id=None) -> SlaDeadlines:
        """Service-specific policy if one exists, else the '*' default. Raises MissingSlaError if neither."""
        policy = self._policies.get_for(priority, service_id or "*")
        if policy is None: raise MissingSlaError(f"No SLA policy configured for {priority.name}")
        return SlaDeadlines(created_at + timedelta(minutes=policy.response_minutes),
                            created_at + timedelta(minutes=policy.resolution_minutes))

    def scan(self) -> list:
        """TODO(Gaurav). Runs every ITSM_SCAN_SECONDS in a background thread (app/services/scheduler.py) + admin 'scan now'.
        Data: self._incidents.list_unresolved(); incident.sla.response_due / .resolution_due; incident.acknowledged_at.
        Response deadline applies until acknowledged_at is set; resolution deadline until the incident is RESOLVED.
        For each breach: `if self._violations.record(incident.id, kind, now):` publish the event ONLY when it returns True
        (that is what makes repeated scans, or several workers, safe). Kinds: RESPONSE_WARNING, RESPONSE_VIOLATION,
        RESOLUTION_WARNING, RESOLUTION_VIOLATION; warn at ~75% of the window. Use self._clock.now(), never datetime.now(),
        and pass timestamp=now when building IncidentEvent. Optional extra: escalate unacknowledged P1s along user.reports_to."""
        raise NotImplementedError("TODO(Gaurav)")
