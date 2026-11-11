"""Builds the object graph once (manual dependency injection - like wiring beans by hand in Java)."""
from app.repositories.sqlite_repos import *
from app.domain.events import EventBus
from app.services.audit import AuditObserver
from app.services.auth_service import AuthService
from app.services.incident_service import IncidentService
from app.services.priority import FixedPriority
from app.services.sla_service import SlaService, Clock

class Container:
    def __init__(self, db_path=":memory:"):
        self.db = Database(db_path); self.db.init_schema()
        self.users = SqliteUserRepository(self.db); self.incidents = SqliteIncidentRepository(self.db)
        self.audit = SqliteAuditRepository(self.db); self.services = SqliteServiceRepository(self.db)
        self.sla_policies = SqliteSlaPolicyRepository(self.db)
        self.bus = EventBus(); self.bus.subscribe(AuditObserver(self.audit).on_event)
        # TODO(Gaurav): self.bus.subscribe(NotificationService([InAppChannel(), SimulatedEmailChannel()]).on_event)
        self.auth = AuthService(self.users)
        self.priority = FixedPriority()        # TODO(Pradhyumn): ScoredPriority()
        self.sla = SlaService(self.sla_policies, self.incidents, self.bus, Clock())
        self.incident_service = IncidentService(self.incidents, self.services, self.bus, self.priority)

def build_container(db_path=":memory:") -> Container: return Container(db_path)
