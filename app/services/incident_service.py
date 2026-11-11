"""Application service: the ONLY place that coordinates incident use cases (owner: Kevalin).
Rules: actor comes from the logged-in session, never from a form field; services never touch SQL or HTTP."""
from app.domain.enums import Role
from app.domain.exceptions import NotFoundError, AuthorizationError
from app.domain.events import *
from app.domain.models import Incident

class IncidentService:
    def __init__(self, incidents, services, bus, priority_strategy):
        self._incidents, self._services, self._bus, self._priority = incidents, services, bus, priority_strategy

    def _publish(self, etype, inc, actor, old, text):
        self._bus.publish(IncidentEvent(etype, inc.id, actor.id if actor else None, old, inc.status.value, text))

    def create_incident(self, reporter, title, description, category, service_id, impact, urgency, affected_users=1) -> Incident:
        service = self._services.get(service_id)
        if service is None: raise NotFoundError(f"Service {service_id} not found")
        inc = Incident(reporter.id, title, description, category, service_id, impact, urgency, affected_users)
        self._incidents.save(inc)
        self._publish(EV_CREATED, inc, reporter, None, f"Incident created by {reporter.name}")
        old = inc.status.value
        inc.classify(); inc.set_priority(self._priority.calculate(inc, service)); self._incidents.save(inc)
        self._publish(EV_CLASSIFIED, inc, None, old, f"Classified as {inc.category.value}, priority {inc.priority.name}")
        return inc

    def get_incident(self, actor, incident_id) -> Incident:
        inc = self._incidents.get(incident_id)
        if inc is None: raise NotFoundError(f"Incident {incident_id} not found")
        if actor.role == Role.EMPLOYEE and inc.reporter_id != actor.id: raise AuthorizationError("Not your incident")
        # TODO(Pradhyumn): technicians may only view incidents assigned to them
        return inc

    def list_for(self, actor) -> list[Incident]:
        if actor.role == Role.EMPLOYEE: return self._incidents.list_by_reporter(actor.id)
        raise NotImplementedError("TODO: technician -> assigned incidents (Pradhyumn); admin -> search() (Gaurav)")

    # ---- Use cases still to implement. Each: check actor role/ownership -> call incident.<transition>() ->
    # ---- save -> _publish(event). InvalidTransitionError comes free from the State objects.
    def assign_incident(self, actor, incident_id, technician_id=None): raise NotImplementedError("TODO(Pradhyumn+Kevalin): use AssignmentStrategy")
    def acknowledge(self, actor, incident_id): raise NotImplementedError("TODO(Kevalin): only the ASSIGNED technician")
    def start_investigation(self, actor, incident_id): raise NotImplementedError("TODO(Kevalin)")
    def add_note(self, actor, incident_id, text, internal=True): raise NotImplementedError("TODO(Pradhyumn)")
    def request_info(self, actor, incident_id, question): raise NotImplementedError("TODO(Pradhyumn)")
    def reply(self, actor, incident_id, answer): raise NotImplementedError("TODO(Kevalin): reporter only")
    def resolve(self, actor, incident_id, resolution): raise NotImplementedError("TODO(Kevalin)")
    def verify(self, actor, incident_id): raise NotImplementedError("TODO(Kevalin): reporter only")
    def reject_resolution(self, actor, incident_id, reason): raise NotImplementedError("TODO(Kevalin)")
    def close(self, actor, incident_id): raise NotImplementedError("TODO(Kevalin): reporter or admin")
