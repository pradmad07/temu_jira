from app.domain.enums import Category
from app.domain.models import Incident, Service

def make_incident(**kw):
    d = dict(reporter_id="U-E1", title="Payment app down", description="Users cannot pay", category=Category.APPLICATION,
             service_id="SVC-PAY", impact=3, urgency=3, affected_users=1)
    d.update(kw); return Incident(**d)

def make_service(**kw):
    d = dict(id="SVC-PAY", name="Payment App", criticality=3); d.update(kw); return Service(**d)
