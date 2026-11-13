"""Employee pages (owner: Kevalin). TODO: reply to info requests, verify/reject resolution, feedback form."""
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from app.domain.permissions import Perm
from .deps import templates, container, require_permission

router = APIRouter(prefix="/employee")
employee = Depends(require_permission(Perm.INCIDENT_VIEW_OWN))

@router.get("/incidents")
def list_incidents(request: Request, user=employee):
    return templates.TemplateResponse(request, "incidents_list.html", {"user": user, "incidents": container(request).incident_service.list_for(user)})

@router.get("/incidents/new")
def new_form(request: Request, user=employee):
    return templates.TemplateResponse(request, "incident_new.html", {"user": user, "services": container(request).services.list_all(), "categories": container(request).categories.list_active()})

@router.post("/incidents/new")
def create(request: Request, user=employee, title: str = Form(), description: str = Form(), category: str = Form(),
           service_id: str = Form(), impact: int = Form(), urgency: int = Form(), affected_users: int = Form(1)):
    inc = container(request).incident_service.create_incident(user, title, description, category, service_id, impact, urgency, affected_users)
    return RedirectResponse(f"/employee/incidents/{inc.id}", 303)

@router.get("/incidents/{incident_id}")
def detail(request: Request, incident_id: str, user=employee):
    c = container(request)
    return templates.TemplateResponse(request, "incident_detail.html", {"user": user, "incident": c.incident_service.get_incident(user, incident_id), "history": c.audit.list_for_incident(incident_id)})
