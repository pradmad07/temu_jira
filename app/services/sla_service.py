"""SLA engine (owner: Gaurav). Clock is injectable so tests/demos never wait real minutes."""
from datetime import datetime, timedelta
from app.domain.models import utcnow

class Clock:
    def now(self) -> datetime: return utcnow()

class SlaService:
    def __init__(self, policies, incidents, bus, clock: Clock):
        self._policies, self._incidents, self._bus, self._clock = policies, incidents, bus, clock
    def deadlines_for(self, priority, created_at: datetime) -> tuple[datetime, datetime]:
        """(response_deadline, resolution_deadline) from the SLA policy. Raise MissingSlaError if none."""
        raise NotImplementedError("TODO(Gaurav)")
    def scan(self) -> list:
        """Run periodically (+ admin 'scan now' button). Publish EV_SLA_WARNING at ~75% of a deadline and
        EV_SLA_VIOLATED after it; record each violation ONCE (sla_violations PK). Also: escalate unacknowledged P1s."""
        raise NotImplementedError("TODO(Gaurav)")
