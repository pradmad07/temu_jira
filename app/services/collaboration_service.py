"""Notes, information requests/replies, and feedback (owner: Pradhyumn for technician UI, Kevalin for employee UI)."""
from app.domain.enums import CommentKind, Status
from app.domain.events import *
from app.domain.exceptions import NotFoundError, AuthorizationError, ValidationError
from app.domain.models import Comment, Feedback
from app.domain.permissions import Perm, can_view_incident

class CollaborationService:
    def __init__(self, incidents, comments, feedback, bus, clock):
        self._incidents, self._comments, self._feedback, self._bus, self._clock = incidents, comments, feedback, bus, clock
    def _load(self, incident_id):
        inc = self._incidents.get(incident_id)
        if inc is None: raise NotFoundError(f"Incident {incident_id} not found")
        return inc
    def _add(self, inc, actor, kind, body, internal, event, text):
        if not (body or "").strip(): raise ValidationError("Text is required")
        self._comments.add(Comment(inc.id, actor.id, kind.value, body.strip(), internal, self._clock.now()))
        s = inc.status.value
        self._bus.publish(IncidentEvent(event, inc.id, actor.id, s, s, text, timestamp=self._clock.now()))
    def _tech(self, actor, inc):
        if not (actor.can(Perm.INCIDENT_WORK) and inc.assigned_to == actor.id): raise AuthorizationError("Only the assigned technician can do that")

    def add_note(self, actor, incident_id, text, internal=True):
        inc = self._load(incident_id); self._tech(actor, inc)
        self._add(inc, actor, CommentKind.NOTE, text, internal, EV_NOTE_ADDED, f"Investigation note added by {actor.name}")
    def request_info(self, actor, incident_id, question):
        inc = self._load(incident_id); self._tech(actor, inc)
        self._add(inc, actor, CommentKind.REQUEST, question, False, EV_INFO_REQUESTED, f"{actor.name} asked the reporter for more information")
    def reply(self, actor, incident_id, answer):
        inc = self._load(incident_id)
        if inc.reporter_id != actor.id: raise AuthorizationError("Only the reporter can reply")
        if inc.status == Status.CLOSED: raise ValidationError("This incident is closed")
        self._add(inc, actor, CommentKind.REPLY, answer, False, EV_INFO_PROVIDED, f"{actor.name} provided more information")
    def list_comments(self, actor, incident_id):
        inc = self._load(incident_id)
        if not can_view_incident(actor, inc): raise AuthorizationError("You are not allowed to view this incident")
        staff = actor.can(Perm.INCIDENT_WORK) or actor.can(Perm.INCIDENT_VIEW_ALL)
        return self._comments.list_for_incident(inc.id, include_internal=staff)   # internal notes never reach the reporter

    def submit_feedback(self, actor, incident_id, rating, comment=""):
        inc = self._load(incident_id)
        if inc.reporter_id != actor.id: raise AuthorizationError("Only the reporter can rate the resolution")
        if inc.status not in (Status.RESOLVED, Status.VERIFIED, Status.CLOSED): raise ValidationError("Feedback is possible after resolution")
        if self._feedback.get(inc.id): raise ValidationError("Feedback was already submitted")
        self._feedback.add(Feedback(inc.id, actor.id, rating, comment))
        s = inc.status.value
        self._bus.publish(IncidentEvent(EV_FEEDBACK, inc.id, actor.id, s, s, f"Reporter rated the resolution {rating}/5", timestamp=self._clock.now()))
