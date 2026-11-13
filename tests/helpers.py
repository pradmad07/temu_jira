from app.domain.enums import Category
from app.domain.models import Incident, Service

def make_incident(**kw):
    d = dict(reporter_id="U-E1", title="Payment app down", description="Users cannot pay", category=Category.APPLICATION,
             service_id="SVC-PAY", impact=3, urgency=3, affected_users=1)
    d.update(kw); return Incident(**d)

def make_service(**kw):
    d = dict(id="SVC-PAY", name="Payment App", criticality=3); d.update(kw); return Service(**d)

from datetime import datetime, timedelta, timezone

class FakeClock:
    """Drop-in for Clock. c.clock.advance(minutes=31) jumps time forward so SLA breaches can be tested instantly."""
    def __init__(self, start=None): self._now = start or datetime(2026, 11, 14, 10, 0, tzinfo=timezone.utc)
    def now(self): return self._now
    def advance(self, minutes=0): self._now += timedelta(minutes=minutes)

from app.domain.enums import Category

def report(c, email="e1@itsm.local", service="SVC-DB", category=Category.DATABASE, impact=3, urgency=3):
    """Employee reports an incident through the real service."""
    return c.incident_service.create_incident(c.users.get_by_email(email), "Queries slow", "Reports time out", category, service, impact, urgency, 5)

def user(c, email): return c.users.get_by_email(email)
