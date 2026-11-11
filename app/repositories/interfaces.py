"""REPOSITORY PATTERN contracts. Services depend on these, never on SQL."""
from abc import ABC, abstractmethod
from typing import Optional
from app.domain.models import User, Technician, Incident, AuditRecord, Service, SlaPolicy
from app.domain.enums import Priority

class UserRepository(ABC):
    @abstractmethod
    def add(self, user: User) -> None: ...
    @abstractmethod
    def get(self, user_id: str) -> Optional[User]: ...
    @abstractmethod
    def get_by_email(self, email: str) -> Optional[User]: ...
    @abstractmethod
    def list_technicians(self) -> list[Technician]: ...

class IncidentRepository(ABC):
    @abstractmethod
    def save(self, incident: Incident) -> None: """Insert or update."""
    @abstractmethod
    def get(self, incident_id: str) -> Optional[Incident]: ...
    @abstractmethod
    def list_by_reporter(self, user_id: str) -> list[Incident]: ...
    @abstractmethod
    def count_active_by_technician(self, technician_id: str) -> int: ...
    @abstractmethod
    def search(self, **filters) -> list[Incident]:
        """Filters: id, status, priority, category, service_id, technician_id, date_from, date_to, text, sla_status."""

class AuditRepository(ABC):
    @abstractmethod
    def append(self, record: AuditRecord) -> None: ...   # append-only: no update/delete on purpose
    @abstractmethod
    def list_for_incident(self, incident_id: str) -> list[AuditRecord]: ...

class ServiceRepository(ABC):
    @abstractmethod
    def get(self, service_id: str) -> Optional[Service]: ...
    @abstractmethod
    def list_all(self) -> list[Service]: ...

class SlaPolicyRepository(ABC):
    @abstractmethod
    def get_for_priority(self, priority: Priority) -> Optional[SlaPolicy]: ...
