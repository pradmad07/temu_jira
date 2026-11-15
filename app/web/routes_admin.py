"""Admin pages & operations center (owner: Gaurav).
Filterable incident table, KPI reports, audit trail, manual SLA scan trigger, and management screens."""
from typing import Optional
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from app.domain.enums import Role, Priority, Status
from app.domain.filters import IncidentFilter
from app.domain.permissions import Perm
from .deps import templates, container, require_permission

router = APIRouter(prefix="/admin")

admin_reporter = Depends(require_permission(Perm.ADMIN_REPORTS, Perm.INCIDENT_VIEW_ALL))
admin_config = Depends(require_permission(Perm.ADMIN_CONFIG))
admin_users = Depends(require_permission(Perm.ADMIN_USERS))
admin_audit_perm = Depends(require_permission(Perm.ADMIN_AUDIT))

# ----------------- Dashboard & Reports -----------------
@router.get("")
def dashboard(request: Request, user=admin_reporter):
    c = container(request)
    overview = c.reports.overview()
    workload = c.reports.technician_workload()
    service_counts = c.reports.service_counts()
    strategy = c.admin.get_assignment_strategy()
    recent_audit = c.audit.list_all(limit=10)
    return templates.TemplateResponse(
        request, "admin_dashboard.html",
        {
            "user": user,
            "overview": overview,
            "workload": workload,
            "service_counts": service_counts,
            "strategy": strategy,
            "recent_audit": recent_audit,
        }
    )

@router.post("/sla/scan")
def trigger_sla_scan(request: Request, user=admin_reporter):
    c = container(request)
    events = c.sla.scan()
    msg = f"SLA scan completed: {len(events)} event(s) published"
    return RedirectResponse(f"/admin?msg={msg}", 303)

@router.post("/strategy")
def set_strategy(request: Request, user=admin_config, strategy: str = Form()):
    c = container(request)
    c.admin.set_assignment_strategy(user, strategy)
    return RedirectResponse(f"/admin?msg=Assignment+strategy+updated+to+{strategy}", 303)

# ----------------- Incident Operations Center -----------------
@router.get("/incidents")
def list_incidents(
    request: Request,
    user=admin_reporter,
    text: Optional[str] = None,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    category: Optional[str] = None,
    service_id: Optional[str] = None,
    sla_status: Optional[str] = None,
):
    c = container(request)
    st = Status(status) if status else None
    pr = Priority[priority] if priority else None
    f = IncidentFilter(
        text=text or None,
        status=st,
        priority=pr,
        category=category or None,
        service_id=service_id or None,
        sla_status=sla_status or None,
    )
    incidents = c.incidents.search(f, limit=100)
    return templates.TemplateResponse(
        request, "admin_incidents.html",
        {
            "user": user,
            "incidents": incidents,
            "statuses": list(Status),
            "priorities": list(Priority),
            "categories": c.categories.list_active(),
            "services": c.services.list_all(),
            "filters": {
                "text": text,
                "status": status,
                "priority": priority,
                "category": category,
                "service_id": service_id,
                "sla_status": sla_status,
            },
        }
    )

# ----------------- Users Management -----------------
@router.get("/users")
def list_users(request: Request, user=admin_users):
    c = container(request)
    all_users = c.users.list_all()
    managers = [u for u in all_users if u.role in (Role.ADMIN, Role.IT_MANAGER, Role.TEAM_LEAD)]
    return templates.TemplateResponse(
        request, "admin_users.html",
        {
            "user": user,
            "users": all_users,
            "managers": managers,
        }
    )

@router.post("/users/new")
def create_user(
    request: Request,
    user=admin_users,
    name: str = Form(),
    email: str = Form(),
    password: str = Form(),
    role: str = Form(),
    reports_to: Optional[str] = Form(None),
    skills: Optional[str] = Form(None),
    max_workload: int = Form(5),
):
    c = container(request)
    target_role = Role(role)
    extra_attrs = {}
    if target_role == Role.TECHNICIAN:
        skill_list = [s.strip().upper() for s in (skills or "").split(",") if s.strip()]
        extra_attrs["skills"] = skill_list
        extra_attrs["max_workload"] = max_workload

    c.admin.create_user(
        user, target_role, name, email, password,
        reports_to=reports_to or None, **extra_attrs
    )
    return RedirectResponse("/admin/users?msg=User+created+successfully", 303)

@router.post("/users/{user_id}/toggle-active")
def toggle_user_active(request: Request, user_id: str, user=admin_users, active: int = Form()):
    c = container(request)
    c.admin.set_user_active(user, user_id, bool(active))
    status_str = "activated" if active else "deactivated"
    return RedirectResponse(f"/admin/users?msg=User+{status_str}+successfully", 303)

# ----------------- Services & SLA Management -----------------
@router.get("/services")
def list_services_and_sla(request: Request, user=admin_config):
    c = container(request)
    return templates.TemplateResponse(
        request, "admin_services_sla.html",
        {
            "user": user,
            "services": c.services.list_all(),
            "sla_policies": c.sla_policies.list_all(),
            "categories": c.categories.list_active(),
        }
    )

@router.post("/services/new")
def create_service(request: Request, user=admin_config, name: str = Form(), criticality: int = Form()):
    c = container(request)
    c.admin.add_service(user, name, criticality)
    return RedirectResponse("/admin/services?msg=Service+added+successfully", 303)

@router.post("/sla-policies")
def set_sla_policy(
    request: Request,
    user=admin_config,
    priority: str = Form(),
    response_minutes: int = Form(),
    resolution_minutes: int = Form(),
    service_id: str = Form("*"),
):
    c = container(request)
    c.admin.set_sla_policy(
        user, Priority[priority], response_minutes, resolution_minutes, service_id=service_id
    )
    return RedirectResponse("/admin/services?msg=SLA+policy+updated+successfully", 303)

@router.post("/categories/new")
def create_category(request: Request, user=admin_config, name: str = Form()):
    c = container(request)
    c.admin.add_category(user, name)
    return RedirectResponse("/admin/services?msg=Category+added+successfully", 303)

@router.post("/categories/{category_name}/disable")
def disable_category(request: Request, category_name: str, user=admin_config):
    c = container(request)
    c.admin.disable_category(user, category_name)
    return RedirectResponse("/admin/services?msg=Category+disabled+successfully", 303)

# ----------------- Audit Trail -----------------
@router.get("/audit")
def view_audit_log(request: Request, user=admin_audit_perm):
    c = container(request)
    records = c.audit.list_all(limit=200)
    return templates.TemplateResponse(
        request, "admin_audit.html",
        {
            "user": user,
            "records": records,
        }
    )
