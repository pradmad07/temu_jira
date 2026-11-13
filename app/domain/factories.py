"""FACTORY PATTERN: the one place that knows which concrete class each role needs."""
from .enums import Role
from .exceptions import ValidationError
from .models import User, Technician

class UserFactory:
    @staticmethod
    def create(role: Role, name, email, password_hash, id=None, reports_to=None, active=True, **technician_attrs) -> User:
        if role == Role.TECHNICIAN:
            return Technician(name, email, password_hash, id=id, reports_to=reports_to, active=active, **technician_attrs)
        if technician_attrs: raise ValidationError(f"Skills/workload only apply to technicians, not {role.value}")
        return User(name, email, password_hash, role, id=id, reports_to=reports_to, active=active)
