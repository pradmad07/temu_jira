"""Admin use cases (owner: Gaurav builds the pages on top of these). Every change is permission-checked and audited."""
from app.domain.enums import Role, Priority
from app.domain.events import IncidentEvent, EV_CONFIG_CHANGED, EV_USER_CHANGED
from app.domain.exceptions import AuthorizationError, NotFoundError, ValidationError
from app.domain.factories import UserFactory
from app.domain.models import Service, SlaPolicy, new_id
from app.domain.permissions import Perm
from .assignment import strategy_by_name, DEFAULT_STRATEGY
from .auth_service import AuthService

class AdminService:
    def __init__(self, categories, users, services, sla_policies, config, bus, clock):
        self._categories, self._users, self._services = categories, users, services
        self._policies, self._config, self._bus, self._clock = sla_policies, config, bus, clock
    def _require(self, actor, perm):
        if not actor.can(perm): raise AuthorizationError("You are not allowed to do that")
    def _audit(self, actor, etype, text):
        self._bus.publish(IncidentEvent(etype, None, actor.id, None, None, text, timestamp=self._clock.now()))

    # categories
    def list_categories(self): return self._categories.list_active()
    def add_category(self, actor, name):
        self._require(actor, Perm.ADMIN_CONFIG); self._categories.add(name); self._audit(actor, EV_CONFIG_CHANGED, f"Category added: {name.strip().upper()}")
    def disable_category(self, actor, name):
        self._require(actor, Perm.ADMIN_CONFIG); self._categories.set_active(name, False); self._audit(actor, EV_CONFIG_CHANGED, f"Category disabled: {name.strip().upper()}")

    # services
    def add_service(self, actor, name, criticality):
        self._require(actor, Perm.ADMIN_CONFIG)
        if not (name or "").strip() or not 1 <= criticality <= 5: raise ValidationError("Service needs a name and criticality 1-5")
        if any(s.name.lower() == name.strip().lower() for s in self._services.list_all()): raise ValidationError("Service already exists")
        svc = Service(new_id("SVC"), name.strip(), criticality); self._services.add(svc)
        self._audit(actor, EV_CONFIG_CHANGED, f"Service added: {svc.name} (criticality {criticality})"); return svc

    # SLA policies
    def set_sla_policy(self, actor, priority: Priority, response_minutes, resolution_minutes, service_id="*"):
        self._require(actor, Perm.ADMIN_CONFIG)
        if response_minutes <= 0 or resolution_minutes < response_minutes: raise ValidationError("Need 0 < response <= resolution (minutes)")
        if service_id != "*" and self._services.get(service_id) is None: raise NotFoundError(f"Service {service_id} not found")
        self._policies.upsert(SlaPolicy(priority, response_minutes, resolution_minutes, service_id))
        self._audit(actor, EV_CONFIG_CHANGED, f"SLA {priority.name} for {service_id}: respond {response_minutes}m, resolve {resolution_minutes}m")

    # assignment strategy
    def get_assignment_strategy(self): return self._config.get("assignment_strategy", DEFAULT_STRATEGY)
    def set_assignment_strategy(self, actor, name):
        self._require(actor, Perm.ADMIN_CONFIG); strategy_by_name(name)    # raises ValidationError for unknown names
        self._config.set("assignment_strategy", name); self._audit(actor, EV_CONFIG_CHANGED, f"Assignment strategy set to {name}")

    # users
    def create_user(self, actor, role: Role, name, email, password, reports_to=None, **technician_attrs):
        self._require(actor, Perm.ADMIN_USERS)
        if len(password or "") < 8: raise ValidationError("Password must be at least 8 characters")
        if self._users.get_by_email(email or ""): raise ValidationError("Email already registered")
        if reports_to and self._users.get(reports_to) is None: raise NotFoundError(f"User {reports_to} not found")
        user = UserFactory.create(role, name, email, AuthService.hash_password(password), reports_to=reports_to, **technician_attrs)
        self._users.add(user); self._audit(actor, EV_USER_CHANGED, f"User created: {user.email} as {role.value}"); return user
    def set_user_active(self, actor, user_id, active: bool):
        self._require(actor, Perm.ADMIN_USERS)
        if user_id == actor.id and not active: raise ValidationError("You cannot deactivate your own account")
        if self._users.get(user_id) is None: raise NotFoundError(f"User {user_id} not found")
        self._users.set_active(user_id, active); self._audit(actor, EV_USER_CHANGED, f"User {user_id} {'activated' if active else 'deactivated'}")
