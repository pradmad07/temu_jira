"""REPOSITORY PATTERN contracts. Services depend on these, never on SQL. Swap the database = write new implementations."""
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional
from app.domain.models import User, Technician, Incident, AuditRecord, Service, SlaPolicy, Comment, Feedback
from app.domain.enums import Priority
from app.domain.filters import IncidentFilter, AuditFilter

class UserRepository(ABC):
    @abstractmethod
    def add(self, user: User) -> None: ...
    @abstractmethod
    def get(self, user_id: str) -> Optional[User]: ...
    @abstractmethod
    def get_by_email(self, email: str) -> Optional[User]: ...
    @abstractmethod
    def list_technicians(self) -> list[Technician]: ...
    @abstractmethod
    def list_all(self) -> list[User]: ...
    @abstractmethod
    def set_active(self, user_id: str, active: bool) -> None: ...
    @abstractmethod
    def set_password_hash(self, user_id: str, password_hash: str) -> None: """Used to upgrade old hashes at login."""

class IncidentRepository(ABC):
    @abstractmethod
    def save(self, incident: Incident) -> None: """Insert or update."""
    @abstractmethod
    def get(self, incident_id: str) -> Optional[Incident]: ...
    @abstractmethod
    def list_by_reporter(self, user_id: str) -> list[Incident]: ...
    @abstractmethod
    def list_by_assignee(self, technician_id: str) -> list[Incident]: """Everything assigned to them that is not CLOSED."""
    @abstractmethod
    def list_unresolved(self) -> list[Incident]: """Status NEW..IN_PROGRESS. Used by the SLA scan."""
    @abstractmethod
    def count_active_by_technician(self, technician_id: str) -> int: ...
    @abstractmethod
    def search(self, f: IncidentFilter, limit: int = 50, offset: int = 0) -> list[Incident]: ...
    @abstractmethod
    def count_total(self) -> int:
        """Total number of incidents across all statuses."""

    @abstractmethod
    def count_by_status(self, statuses: tuple) -> int:
        """Number of incidents whose status is one of `statuses`."""

    @abstractmethod
    def count_critical(self) -> int:
        """Number of P1 incidents across all statuses (including resolved ones)."""

    @abstractmethod
    def technician_workload(self) -> list[tuple]:
        """Per active technician, (name, active_count, technician_id, max_workload),
        sorted by active_count desc then name asc."""

    @abstractmethod
    def counts_by_service(self) -> list[tuple]:
        """Per service, (name, incident_count, service_id),
        sorted by incident_count desc then name asc."""

class AuditRepository(ABC):
    @abstractmethod
    def append(self, record: AuditRecord) -> None: ...   # append-only: no update/delete on purpose
    @abstractmethod
    def list_for_incident(self, incident_id: str) -> list[AuditRecord]: ...
    @abstractmethod
    def list_all(self, limit: int = 200) -> list[AuditRecord]: """Newest first (admin audit log)."""
    @abstractmethod
    def search(self, f: Optional[AuditFilter] = None, limit: int = 200, offset: int = 0) -> list[AuditRecord]: ...
    @abstractmethod
    def list_actions(self) -> list[str]: ...

class ServiceRepository(ABC):
    @abstractmethod
    def get(self, service_id: str) -> Optional[Service]: ...
    @abstractmethod
    def list_all(self) -> list[Service]: ...
    @abstractmethod
    def add(self, service: Service) -> None: ...
    @abstractmethod
    def update_criticality(self, service_id: str, criticality: int) -> None: ...

class SlaPolicyRepository(ABC):
    @abstractmethod
    def get_for(self, priority: Priority, service_id: str = "*") -> Optional[SlaPolicy]: """Service-specific policy, else the '*' default."""
    @abstractmethod
    def upsert(self, policy: SlaPolicy) -> None: ...
    @abstractmethod
    def list_all(self) -> list[SlaPolicy]: ...

class CategoryRepository(ABC):
    @abstractmethod
    def list_active(self) -> list[str]: ...
    @abstractmethod
    def exists_active(self, name: str) -> bool: ...
    @abstractmethod
    def add(self, name: str) -> None: """Create, or re-enable if it was disabled."""
    @abstractmethod
    def set_active(self, name: str, active: bool) -> None: """Disable, never delete: old incidents keep their category."""
    @abstractmethod
    def ensure_defaults(self, names) -> None: ...

class SlaViolationRepository(ABC):
    @abstractmethod
    def record(self, incident_id: str, kind: str, detected_at) -> bool:
        """Insert once per (incident, kind). Returns True only if newly recorded, so callers publish events once."""
    @abstractmethod
    def list_for_incident(self, incident_id: str) -> list[tuple]: ...
    @abstractmethod
    def list_all(self) -> list[tuple]: ...

class CommentRepository(ABC):
    @abstractmethod
    def add(self, comment: Comment) -> None: ...
    @abstractmethod
    def list_for_incident(self, incident_id: str, include_internal: bool = True) -> list[Comment]: ...

class FeedbackRepository(ABC):
    @abstractmethod
    def add(self, feedback: Feedback) -> None: ...
    @abstractmethod
    def get(self, incident_id: str) -> Optional[Feedback]: ...

class ConfigRepository(ABC):
    @abstractmethod
    def get(self, key: str, default: Optional[str] = None) -> Optional[str]: ...
    @abstractmethod
    def set(self, key: str, value: str) -> None: ...

class NotificationRepository(ABC):
    @abstractmethod
    def add(self, recipient_id: str, channel: str, subject: str, body: str, status: str = "SENT", created_at: Optional[datetime] = None) -> int: ...
    @abstractmethod
    def list_for_recipient(self, recipient_id: str, unread_only: bool = False, channel: Optional[str] = None) -> list[dict]:
        """Newest first. Optional channel filter; None = all channels."""
    @abstractmethod
    def count_unread(self, recipient_id: str, channel: str = "IN_APP") -> int:
        """SQL COUNT of unread rows for this recipient in the given channel (navbar bell)."""
    @abstractmethod
    def mark_read(self, notification_id: int, recipient_id: str) -> None:
        """Sets is_read=1 only when the row belongs to recipient_id; otherwise silently does nothing."""
    @abstractmethod
    def mark_all_read(self, recipient_id: str) -> None: ...
