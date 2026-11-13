"""Role -> permission mapping (single source of truth). Code asks "can this user do X?", never "is this user an ADMIN?".
Coarse permissions live here. Relationship checks (is it YOUR incident? the ASSIGNED technician?) live in services,
except the one shared read rule, can_view_incident(), kept here so every service applies it identically."""
from .enums import Role

class Perm:
    INCIDENT_CREATE = "incident.create"
    INCIDENT_VIEW_OWN = "incident.view_own"
    INCIDENT_VIEW_ASSIGNED = "incident.view_assigned"
    INCIDENT_VIEW_ALL = "incident.view_all"
    INCIDENT_ASSIGN = "incident.assign"        # triage: assign, reassign, change priority
    INCIDENT_WORK = "incident.work"            # acknowledge, start, note, request info, resolve
    ADMIN_USERS = "admin.users"
    ADMIN_CONFIG = "admin.config"              # categories, services, SLA policies, assignment strategy
    ADMIN_REPORTS = "admin.reports"
    ADMIN_AUDIT = "admin.audit"

ROLE_PERMISSIONS: dict = {
    Role.EMPLOYEE: frozenset({Perm.INCIDENT_CREATE, Perm.INCIDENT_VIEW_OWN}),
    Role.TECHNICIAN: frozenset({Perm.INCIDENT_VIEW_ASSIGNED, Perm.INCIDENT_WORK}),
    Role.TEAM_LEAD: frozenset({Perm.INCIDENT_VIEW_ASSIGNED, Perm.INCIDENT_WORK, Perm.INCIDENT_ASSIGN}),
    Role.ADMIN: frozenset({Perm.INCIDENT_VIEW_ALL, Perm.INCIDENT_ASSIGN, Perm.ADMIN_USERS, Perm.ADMIN_CONFIG,
                           Perm.ADMIN_REPORTS, Perm.ADMIN_AUDIT}),
    Role.IT_MANAGER: frozenset({Perm.INCIDENT_VIEW_ALL, Perm.INCIDENT_ASSIGN, Perm.ADMIN_REPORTS, Perm.ADMIN_AUDIT}),
}
# To add a role: add it to Role in enums.py, add a row here. Nothing else needs to change.

def can_view_incident(actor, incident) -> bool:
    return (actor.can(Perm.INCIDENT_VIEW_ALL)
            or (actor.can(Perm.INCIDENT_VIEW_ASSIGNED) and incident.assigned_to == actor.id)
            or (actor.can(Perm.INCIDENT_VIEW_OWN) and incident.reporter_id == actor.id))
