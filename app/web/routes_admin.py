"""Admin pages & operations center (owner: Gaurav).
Filterable incident table, KPI reports, audit trail, manual SLA scan trigger, and management screens."""
from typing import Optional
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from app.domain.enums import Role, Priority, Status
from app.domain.filters import IncidentFilter, AuditFilter
from app.domain.permissions import Perm
from app.services.assignment import strategy_by_name
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

@router.get("/incidents/{incident_id}")
def inspect_incident(request: Request, incident_id: str, user=admin_reporter):
    c = container(request)
    incident = c.incident_service.get_incident(user, incident_id)
    history = c.audit.list_for_incident(incident_id)
    comments = c.collab.list_comments(user, incident_id) if hasattr(c, "collab") else []
    feedback = c.feedback.get(incident_id) if hasattr(c, "feedback") else None
    technicians = c.users.list_technicians()
    workloads = {t.id: c.incidents.count_active_by_technician(t.id) for t in technicians}
    strategy = strategy_by_name(c.config.get("assignment_strategy", "skill"))
    recommendations = strategy.recommend(incident, technicians, workloads)
    return templates.TemplateResponse(
        request, "incident_detail.html",
        {
            "user": user,
            "incident": incident,
            "history": history,
            "comments": comments,
            "feedback": feedback,
            "recommendations": recommendations,
            "technicians": technicians,
        }
    )

@router.post("/incidents/{incident_id}/assign")
def assign_incident(request: Request, incident_id: str, technician_id: str = Form(None), user=admin_reporter):
    c = container(request)
    target = technician_id.strip() if technician_id and technician_id.strip() else None
    c.incident_service.assign_incident(user, incident_id, target)
    return RedirectResponse(f"/admin/incidents/{incident_id}?msg=Technician+assigned+successfully", 303)

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
def view_audit_log(
    request: Request,
    user=admin_audit_perm,
    text: Optional[str] = None,
    action: Optional[str] = None,
    incident_id: Optional[str] = None,
    actor_id: Optional[str] = None,
    sort: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_dir: Optional[str] = None,
):
    c = container(request)

    sb = sort_by or "timestamp"
    sd = sort_dir or "desc"
    if sort:
        parts = sort.rsplit("_", 1)
        if len(parts) == 2 and parts[1].lower() in ("asc", "desc"):
            sb, sd = parts[0], parts[1].lower()
        else:
            sb = sort

    af = AuditFilter(
        text=text or None,
        action=action or None,
        incident_id=incident_id or None,
        actor_id=actor_id or None,
        sort_by=sb,
        sort_dir=sd,
    )
    records = c.audit.search(af, limit=200)
    all_actions = c.audit.list_actions()

    return templates.TemplateResponse(
        request, "admin_audit.html",
        {
            "user": user,
            "records": records,
            "actions": all_actions,
            "filters": {
                "text": text or "",
                "action": action or "",
                "incident_id": incident_id or "",
                "actor_id": actor_id or "",
                "sort_by": sb,
                "sort_dir": sd,
                "sort": f"{sb}_{sd}",
            },
        }
    )
