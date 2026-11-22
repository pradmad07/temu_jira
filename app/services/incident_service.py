"""Incident use cases (owner: Kevalin). Rules: actor comes from the session, never a form field; no SQL, no HTTP in here.
Every state change follows ONE recipe: load -> check who may do it -> ask the State object (via the Incident) ->
save -> publish an event. Audit and notifications react to the event; this class knows nothing about them."""
from app.domain.enums import CommentKind, Status
from app.domain.events import *
from app.domain.exceptions import (NotFoundError, AuthorizationError, ValidationError, InvalidTransitionError,
                                   TechnicianUnavailableError, WorkloadExceededError)
from app.domain.filters import IncidentFilter
from app.domain.models import Comment, Incident, Technician
from app.domain.permissions import Perm, can_view_incident
from .assignment import strategy_by_name, DEFAULT_STRATEGY
import logging

class IncidentService:
    def __init__(self, incidents, services, categories, users, bus, clock,
                 priority_strategy, sla, config, comments):
        self._incidents, self._services, self._categories, self._users = incidents, services, categories, users
        self._bus, self._clock, self._priority, self._sla, self._config = bus, clock, priority_strategy, sla, config
        self._comments = comments

    # ---------- helpers
    def _load(self, incident_id) -> Incident:
        inc = self._incidents.get(incident_id)
        if inc is None: raise NotFoundError(f"Incident {incident_id} not found")
        return inc
    def _publish(self, etype, inc, actor, old, new, text, previous_assignee=None):
        self._bus.publish(IncidentEvent(etype, inc.id, actor.id if actor else None, old, new, text, timestamp=self._clock.now(), previous_assignee=previous_assignee))
    def _apply(self, inc, actor, action, event, text, previous_assignee=None, **kwargs):
        """The shared recipe for every lifecycle change."""
        old = inc.status.value
        getattr(inc, action)(**kwargs)          # the State object may refuse -> InvalidTransitionError
        self._incidents.save(inc)
        self._publish(event, inc, actor, old, inc.status.value, text, previous_assignee=previous_assignee)
        return inc
    @staticmethod
    def _require_assignee(actor, inc):
        if not (actor.can(Perm.INCIDENT_WORK) and inc.assigned_to == actor.id): raise AuthorizationError("Only the assigned technician can do that")
    @staticmethod
    def _require_reporter(actor, inc):
        if inc.reporter_id != actor.id: raise AuthorizationError("Only the person who reported the incident can do that")

    # ---------- create / read
    def create_incident(self, reporter, title, description, category, service_id, impact, urgency, affected_users=1) -> Incident:
        if not reporter.can(Perm.INCIDENT_CREATE): raise AuthorizationError("You cannot report incidents")
        service = self._services.get(service_id)
        if service is None: raise NotFoundError(f"Service {service_id} not found")
        if not self._categories.exists_active(category): raise ValidationError(f"Unknown or disabled category: {category}")
        inc = Incident(reporter.id, title, description, category, service_id, impact, urgency, affected_users, created_at=self._clock.now())
        inc.classify()
        inc.set_priority(self._priority.calculate(inc, service))
        inc.set_sla(self._sla.deadlines_for(inc.priority, inc.created_at, service_id))   # may raise MissingSlaError BEFORE anything is saved
        self._incidents.save(inc)
        self._publish(EV_CREATED, inc, reporter, None, Status.NEW.value, f"Incident created by {reporter.name}")
        self._publish(EV_CLASSIFIED, inc, None, Status.NEW.value, inc.status.value,
                      f"Classified as {inc.category}, priority {inc.priority.name}, resolve by {inc.sla.resolution_due:%H:%M}")
        return inc

    def get_incident(self, actor, incident_id) -> Incident:
        inc = self._load(incident_id)
        if not can_view_incident(actor, inc): raise AuthorizationError("You are not allowed to view this incident")
        return inc

    def list_for(self, actor) -> list[Incident]:
        if actor.can(Perm.INCIDENT_VIEW_ALL): return self._incidents.search(IncidentFilter())   # Gaurav implements search()
        if actor.can(Perm.INCIDENT_VIEW_ASSIGNED): return self._incidents.list_by_assignee(actor.id)
        if actor.can(Perm.INCIDENT_VIEW_OWN): return self._incidents.list_by_reporter(actor.id)
        raise AuthorizationError("You cannot list incidents")

    # ---------- assignment (manual, or through the configured strategy)
    def assign_incident(self, actor, incident_id, technician_id=None) -> Incident:
        """Admin/team lead. technician_id given = manual choice; None = let the configured strategy choose."""
        if not actor.can(Perm.INCIDENT_ASSIGN): raise AuthorizationError("You cannot assign incidents")
        inc = self._load(incident_id)
        if technician_id:
            target = self._users.get(technician_id)
            if target is None: raise NotFoundError(f"User {technician_id} not found")
        else: target = self._choose(inc)
        return self._assign(inc, target, actor)

    def auto_assign(self, incident_id) -> Incident:
        """System action (called by the AutoAssigner observer). Leaves the incident CLASSIFIED for a human if nobody fits."""
        inc = self._load(incident_id)
        return inc if inc.status != Status.CLASSIFIED else self._assign(inc, self._choose(inc), None)
        
    def escalate(self, incident_id) -> Incident:
        """System action: on an unacknowledged P1 SLA breach, reassign to the first manager
        up the current assignee's reports_to chain who can work incidents (has INCIDENT_WORK).
        Returns the incident; does nothing (and logs) when:
        - the incident is unassigned (no chain to walk from),
        - no one up the chain can work incidents,
        - the walk would land on the current owner."""
        inc = self._load(incident_id)
        if inc.assigned_to is None:
            logging.info("Cannot escalate %s: incident is unassigned", incident_id)
            return inc
        current = self._users.get(inc.assigned_to)
        if current is None:
            logging.info("Cannot escalate %s: assignee %s not found", incident_id, inc.assigned_to)
            return inc
        next_id = current.reports_to
        while next_id is not None:
            candidate = self._users.get(next_id)
            if candidate is None:
                logging.info("Cannot escalate %s: manager %s not found", incident_id, next_id)
                return inc
            if candidate.id == inc.assigned_to:
                logging.info("Cannot escalate %s: already owned by %s", incident_id, candidate.name)
                return inc
            if candidate.active and candidate.can(Perm.INCIDENT_WORK):
                try:
                    return self._assign(inc, candidate, None)   # actor=None: system action
                except (TechnicianUnavailableError, WorkloadExceededError) as ex:
                    logging.info("Cannot escalate %s to %s: %s", incident_id, candidate.name, ex)
            next_id = candidate.reports_to
        logging.info("Cannot escalate %s: no qualified manager in chain", incident_id)
        return inc

    def _choose(self, inc):
        strategy = strategy_by_name(self._config.get("assignment_strategy", DEFAULT_STRATEGY))
        candidates = self._users.list_technicians()
        workloads = {t.id: self._incidents.count_active_by_technician(t.id) for t in candidates}
        return strategy.choose(inc, candidates, workloads)

    def _assign(self, inc, target, actor):
        if not target.active or not target.can(Perm.INCIDENT_WORK): raise TechnicianUnavailableError(f"{target.name} cannot take incidents")
        if isinstance(target, Technician):
            if not target.available: raise TechnicianUnavailableError(f"{target.name} is not available")
            if self._incidents.count_active_by_technician(target.id) >= target.max_workload:
                raise WorkloadExceededError(f"{target.name} is at their workload limit ({target.max_workload})")
        first = inc.status == Status.CLASSIFIED
        prev = inc.assigned_to
        how = "" if actor else " automatically"
        return self._apply(inc, actor, "assign" if first else "reassign", EV_ASSIGNED if first else EV_REASSIGNED,
                           f"{'Assigned' if first else 'Reassigned'} to {target.name}{how}",
                           previous_assignee=prev if not first else None,
                           technician_id=target.id)

    def change_priority(self, actor, incident_id, priority, reason) -> Incident:
        if not actor.can(Perm.INCIDENT_ASSIGN): raise AuthorizationError("You cannot change priority")
        if not (reason or "").strip(): raise ValidationError("A reason is required")
        inc = self._load(incident_id)
        if inc.status in (Status.VERIFIED, Status.CLOSED): raise InvalidTransitionError("Cannot reprioritise a finished incident")
        old = inc.priority
        inc.set_priority(priority)
        inc.set_sla(self._sla.deadlines_for(priority, inc.created_at, inc.service_id))   # SLA follows the new priority
        self._incidents.save(inc)
        self._publish(EV_PRIORITY_CHANGED, inc, actor, inc.status.value, inc.status.value,
                      f"Priority {old.name if old else '-'} -> {priority.name}: {reason.strip()}")
        return inc

    # ---------- technician work
    def acknowledge(self, actor, incident_id):
        inc = self._load(incident_id); self._require_assignee(actor, inc)
        return self._apply(inc, actor, "acknowledge", EV_ACKNOWLEDGED, f"Acknowledged by {actor.name}", at=self._clock.now())
    def start_investigation(self, actor, incident_id):
        inc = self._load(incident_id); self._require_assignee(actor, inc)
        return self._apply(inc, actor, "start", EV_STARTED, f"Investigation started by {actor.name}")
    def resolve(self, actor, incident_id, resolution):
        inc = self._load(incident_id); self._require_assignee(actor, inc)
        return self._apply(inc, actor, "resolve", EV_RESOLVED, f"Resolved by {actor.name}", resolution=resolution, at=self._clock.now())

    # ---------- reporter confirms, then closure
    def verify(self, actor, incident_id):
        inc = self._load(incident_id); self._require_reporter(actor, inc)
        return self._apply(inc, actor, "verify", EV_VERIFIED, "Reporter confirmed the fix")
    def reject_resolution(self, actor, incident_id, reason):
        inc = self._load(incident_id); self._require_reporter(actor, inc)
        if not (reason or "").strip(): raise ValidationError("Please say what is still wrong")
        result = self._apply(inc, actor, "reject", EV_REJECTED, f"Reporter says not fixed: {reason.strip()}")
        # Record the reporter's reason as a REPLY comment. We write directly to the repo so
        # we don't publish a second event (EV_REJECTED already fired -> one notification only).
        self._comments.add(Comment(inc.id, actor.id, CommentKind.REPLY.value,
                                   f"Resolution Rejected - Still broken: {reason.strip()}",
                                   False, self._clock.now()))
        return result
    def close(self, actor, incident_id):
        inc = self._load(incident_id)
        if inc.reporter_id != actor.id and not actor.can(Perm.INCIDENT_VIEW_ALL): raise AuthorizationError("Only the reporter or an administrator can close")
        return self._apply(inc, actor, "close", EV_CLOSED, f"Closed by {actor.name}", at=self._clock.now())
