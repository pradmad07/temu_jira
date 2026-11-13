"""Domain model (owner: Kevalin). Private attributes + read-only properties = encapsulation.
Technician IS-A User. Incident delegates lifecycle to State objects and COMPOSES a SlaDeadlines value object.
Other aggregates are referenced by ID (reporter_id, service_id, assigned_to) so an Incident loads on its own - see docs/DESIGN.md."""
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import NamedTuple, Optional
from .enums import Role, Status, Priority, Category
from .exceptions import ValidationError
from .states import state_for
from .permissions import ROLE_PERMISSIONS
import re

def utcnow() -> datetime: return datetime.now(timezone.utc)
def new_id(prefix: str) -> str: return f"{prefix}{uuid.uuid4().hex[:6].upper()}"

_CATEGORY_RE = re.compile(r"^[A-Z][A-Z0-9 _-]{1,39}$")
def normalise_category(name) -> str:
    n = (name or "").strip().upper()
    if not _CATEGORY_RE.match(n): raise ValidationError("Category must be 2-40 characters: letters, digits, space, - or _")
    return n

class SlaDeadlines(NamedTuple):
    """Snapshot taken when the incident is prioritised, so editing a policy later never rewrites history."""
    response_due: datetime
    resolution_due: datetime

class User:
    def __init__(self, name, email, password_hash, role: Role, id=None, reports_to=None, active=True):
        if not name or "@" not in (email or ""): raise ValidationError("A name and a valid email are required")
        self._id = id or new_id("U"); self._name = name; self._email = email.lower()
        self._password_hash = password_hash; self._role = role
        self._reports_to = reports_to; self._active = active   # reports_to = next step in the escalation chain
    id = property(lambda s: s._id); name = property(lambda s: s._name); email = property(lambda s: s._email)
    role = property(lambda s: s._role); password_hash = property(lambda s: s._password_hash)
    reports_to = property(lambda s: s._reports_to); active = property(lambda s: s._active)
    def can(self, permission: str) -> bool: return permission in ROLE_PERMISSIONS.get(self._role, frozenset())

class Technician(User):
    def __init__(self, name, email, password_hash, skills=(), experience_years=0, available=True, max_workload=5, id=None, reports_to=None, active=True):
        super().__init__(name, email, password_hash, Role.TECHNICIAN, id, reports_to, active)
        self._skills = frozenset(s.upper() for s in skills); self._experience = experience_years
        self._available = available; self._max_workload = max_workload
    skills = property(lambda s: s._skills); experience_years = property(lambda s: s._experience)
    available = property(lambda s: s._available); max_workload = property(lambda s: s._max_workload)
    def has_skill(self, category: str) -> bool: return category.strip().upper() in self._skills
    def can_accept(self, active_count: int) -> bool: return self._available and active_count < self._max_workload

@dataclass
class Service: id: str; name: str; criticality: int            # criticality 1 (low) .. 5 (business critical)
@dataclass
class SlaPolicy: priority: Priority; response_minutes: int; resolution_minutes: int; service_id: str = "*"   # "*" = default for every service
@dataclass
class AuditRecord:
    incident_id: str; actor_id: Optional[str]; action: str; old_status: Optional[str]; new_status: Optional[str]
    description: str; timestamp: datetime = field(default_factory=utcnow)
@dataclass
class Comment:
    incident_id: str; author_id: str; kind: str; body: str; internal: bool = False
    created_at: datetime = field(default_factory=utcnow)

@dataclass
class Feedback:
    incident_id: str; reporter_id: str; rating: int; comment: str = ""
    def __post_init__(self):
        if not 1 <= self.rating <= 5: raise ValidationError("Rating must be between 1 and 5")

class Incident:
    def __init__(self, reporter_id, title, description, category: str, service_id, impact, urgency,
                 affected_users=1, id=None, status=Status.NEW, priority: Optional[Priority] = None,
                 assigned_to=None, created_at=None, resolution=None, acknowledged_at=None, resolved_at=None, closed_at=None, sla: Optional[SlaDeadlines] = None):
        if not (title or "").strip() or not (description or "").strip(): raise ValidationError("Title and description are required")
        if len(title) > 200 or len(description) > 5000: raise ValidationError("Title/description too long")
        if not (1 <= impact <= 5 and 1 <= urgency <= 5): raise ValidationError("Impact and urgency must be 1-5")
        if affected_users < 1: raise ValidationError("Affected users must be at least 1")
        self._id = id or new_id("INC"); self._reporter_id = reporter_id; self._title = title.strip()
        self._description = description.strip(); self._category = normalise_category(category); self._service_id = service_id
        self._impact = impact; self._urgency = urgency; self._affected_users = affected_users
        self._priority = priority; self._assigned_to = assigned_to; self._resolution = resolution
        self._created_at = created_at or utcnow(); self._state = state_for(status)
        self._acknowledged_at = acknowledged_at; self._resolved_at = resolved_at
        self._closed_at = closed_at; self._sla = sla
    id = property(lambda s: s._id); reporter_id = property(lambda s: s._reporter_id); title = property(lambda s: s._title)
    description = property(lambda s: s._description); category = property(lambda s: s._category)
    service_id = property(lambda s: s._service_id); impact = property(lambda s: s._impact)
    urgency = property(lambda s: s._urgency); affected_users = property(lambda s: s._affected_users)
    priority = property(lambda s: s._priority); assigned_to = property(lambda s: s._assigned_to)
    resolution = property(lambda s: s._resolution); created_at = property(lambda s: s._created_at)
    status = property(lambda s: s._state.status)
    acknowledged_at = property(lambda s: s._acknowledged_at); resolved_at = property(lambda s: s._resolved_at)
    closed_at = property(lambda s: s._closed_at); sla = property(lambda s: s._sla)

    def set_priority(self, p: Priority): self._priority = p
    def set_sla(self, sla: SlaDeadlines): self._sla = sla
    def _do(self, action): self._state = getattr(self._state, action)(self)   # state object decides legality
    def classify(self): self._do("classify")
    def assign(self, technician_id): self._do("assign"); self._assigned_to = technician_id
    def reassign(self, technician_id): self._do("reassign"); self._assigned_to = technician_id   # first-response time stays as recorded
    def acknowledge(self, at=None): self._do("acknowledge"); self._acknowledged_at = at or utcnow()
    def start(self): self._do("start")
    def resolve(self, resolution: str, at=None):
        if not (resolution or "").strip(): raise ValidationError("A resolution description is required")
        self._do("resolve"); self._resolution = resolution.strip(); self._resolved_at = at or utcnow()
    def verify(self): self._do("verify")
    def reject(self): self._do("reject"); self._resolved_at = None   # not fixed -> clock keeps running
    def close(self, at=None): self._do("close"); self._closed_at = at or utcnow()
