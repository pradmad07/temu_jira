"""Builds the object graph once (manual dependency injection - like wiring beans by hand in Java)."""
import os
from app.repositories.sqlite_repos import *
from app.domain.clock import Clock
from app.domain.enums import Category
from app.domain.events import EventBus
from app.services.admin_service import AdminService
from app.services.audit import AuditObserver
from app.services.auth_service import AuthService
from app.services.auto_assign import AutoAssigner
from app.services.collaboration_service import CollaborationService
from app.services.incident_service import IncidentService
from app.services.priority import FixedPriority
from app.services.sla_service import SlaService
from app.services.notifications import NotificationService, InAppChannel, SimulatedEmailChannel

class Container:
    def __init__(self, db_path=":memory:", clock=None, auto_assign=True):
        self.db = Database(db_path); self.db.init_schema()
        self.clock = clock or Clock()   # tests/demos pass a FakeClock
        self.users = SqliteUserRepository(self.db); self.incidents = SqliteIncidentRepository(self.db)
        self.audit = SqliteAuditRepository(self.db); self.services = SqliteServiceRepository(self.db)
        self.sla_policies = SqliteSlaPolicyRepository(self.db); self.violations = SqliteSlaViolationRepository(self.db)
        self.categories = SqliteCategoryRepository(self.db); self.categories.ensure_defaults(Category.DEFAULTS)
        self.comments = SqliteCommentRepository(self.db); self.feedback = SqliteFeedbackRepository(self.db)
        self.config = SqliteConfigRepository(self.db)
        self.bus = EventBus(); self.bus.subscribe(AuditObserver(self.audit).on_event)   # audit first: it must see every event
        self.notifications = SqliteNotificationRepository(self.db)
        self.notification_service = NotificationService(
            [InAppChannel(self.notifications), SimulatedEmailChannel(self.notifications)],
            users=self.users, incidents=self.incidents
        )
        self.bus.subscribe(self.notification_service.on_event)
        domains = [d.strip().lower() for d in os.environ.get("ITSM_SSO_DOMAINS", "").split(",") if d.strip()]   # e.g. company.com
        self.auth = AuthService(self.users, sso_domains=domains or None)
        self.priority = FixedPriority()        # TODO(Pradhyumn): ScoredPriority()
        self.sla = SlaService(self.sla_policies, self.incidents, self.bus, self.clock, self.violations)
        self.incident_service = IncidentService(self.incidents, self.services, self.categories, self.users, self.bus,
                                                self.clock, self.priority, self.sla, self.config)
        self.collab = CollaborationService(self.incidents, self.comments, self.feedback, self.bus, self.clock)
        self.admin = AdminService(self.categories, self.users, self.services, self.sla_policies, self.config, self.bus, self.clock)
        if auto_assign: self.bus.subscribe(AutoAssigner(self.incident_service).on_event)

def build_container(db_path=":memory:", clock=None, auto_assign=True) -> Container: return Container(db_path, clock, auto_assign)
