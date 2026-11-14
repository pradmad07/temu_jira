"""SLA engine. deadlines_for() is done (Kevalin); scan() and warnings are Gaurav's.
Clock is injectable so tests/demos never wait real minutes."""
from datetime import timedelta
from app.domain.clock import Clock   # re-exported: `from ...sla_service import Clock` still works
from app.domain.enums import Priority, Status
from app.domain.events import IncidentEvent, EV_SLA_WARNING, EV_SLA_VIOLATED, EV_ESCALATED
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
        """Runs every ITSM_SCAN_SECONDS in a background thread (app/services/scheduler.py) + admin 'scan now'.
        Data: self._incidents.list_unresolved(); incident.sla.response_due / .resolution_due; incident.acknowledged_at.
        Response deadline applies until acknowledged_at is set; resolution deadline until the incident is RESOLVED.
        For each breach: `if self._violations.record(incident.id, kind, now):` publish the event ONLY when it returns True
        (that is what makes repeated scans, or several workers, safe). Kinds: RESPONSE_WARNING, RESPONSE_VIOLATION,
        RESOLUTION_WARNING, RESOLUTION_VIOLATION; warn at ~75% of the window. Use self._clock.now(), never datetime.now(),
        and pass timestamp=now when building IncidentEvent. Optional extra: escalate unacknowledged P1s along user.reports_to."""
        now = self._clock.now()
        unresolved = self._incidents.list_unresolved()
        events = []

        for inc in unresolved:
            sla = inc.sla
            if sla is None and inc.priority:
                try:
                    sla = self.deadlines_for(inc.priority, inc.created_at, inc.service_id)
                except MissingSlaError:
                    continue
            if sla is None:
                continue

            created = inc.created_at

            # 1. Response deadline: applies until acknowledged_at is set
            if inc.acknowledged_at is None:
                resp_window = (sla.response_due - created).total_seconds()
                resp_warn_threshold = created + timedelta(seconds=0.75 * resp_window)

                if now >= sla.response_due:
                    if self._violations.record(inc.id, "RESPONSE_VIOLATION", now):
                        ev = IncidentEvent(
                            EV_SLA_VIOLATED, inc.id, None, inc.status.value, inc.status.value,
                            f"Response SLA breached for incident {inc.id}", timestamp=now
                        )
                        self._bus.publish(ev)
                        events.append(ev)

                    # Escalate unacknowledged P1s
                    if inc.priority == Priority.P1:
                        if self._violations.record(inc.id, "P1_ESCALATION", now):
                            ev = IncidentEvent(
                                EV_ESCALATED, inc.id, None, inc.status.value, inc.status.value,
                                f"P1 incident {inc.id} unacknowledged past response deadline - escalated", timestamp=now
                            )
                            self._bus.publish(ev)
                            events.append(ev)

                elif now >= resp_warn_threshold:
                    if self._violations.record(inc.id, "RESPONSE_WARNING", now):
                        ev = IncidentEvent(
                            EV_SLA_WARNING, inc.id, None, inc.status.value, inc.status.value,
                            f"Response SLA warning (75% elapsed) for incident {inc.id}", timestamp=now
                        )
                        self._bus.publish(ev)
                        events.append(ev)

            # 2. Resolution deadline: applies until incident is RESOLVED (or closed)
            if inc.status != Status.RESOLVED and inc.resolved_at is None:
                resol_window = (sla.resolution_due - created).total_seconds()
                resol_warn_threshold = created + timedelta(seconds=0.75 * resol_window)

                if now >= sla.resolution_due:
                    if self._violations.record(inc.id, "RESOLUTION_VIOLATION", now):
                        ev = IncidentEvent(
                            EV_SLA_VIOLATED, inc.id, None, inc.status.value, inc.status.value,
                            f"Resolution SLA breached for incident {inc.id}", timestamp=now
                        )
                        self._bus.publish(ev)
                        events.append(ev)

                elif now >= resol_warn_threshold:
                    if self._violations.record(inc.id, "RESOLUTION_WARNING", now):
                        ev = IncidentEvent(
                            EV_SLA_WARNING, inc.id, None, inc.status.value, inc.status.value,
                            f"Resolution SLA warning (75% elapsed) for incident {inc.id}", timestamp=now
                        )
                        self._bus.publish(ev)
                        events.append(ev)

        return events
