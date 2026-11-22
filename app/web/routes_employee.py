"""Employee pages & lifecycle interactions."""
from urllib.parse import quote_plus
from fastapi import APIRouter, Depends, Request, Form
from fastapi.responses import RedirectResponse
from app.domain.exceptions import ItsmError
from app.domain.permissions import Perm
from .deps import templates, container, require_permission

router = APIRouter(prefix="/employee")
employee = Depends(require_permission(Perm.INCIDENT_VIEW_OWN))

@router.get("/incidents")
def list_incidents(request: Request, user=Depends(require_permission(Perm.INCIDENT_VIEW_OWN, Perm.INCIDENT_VIEW_ALL))):
    c = container(request)
    users_map = {u.id: u for u in c.users.list_all()}
    return templates.TemplateResponse(
        request, "incidents_list.html",
        {
            "user": user,
            "incidents": c.incident_service.list_for(user),
            "reporters": users_map,
        }
    )

@router.get("/incidents/new")
def new_form(request: Request, user=employee):
    return templates.TemplateResponse(
        request, "incident_new.html",
        {
            "user": user,
            "services": container(request).services.list_all(),
            "categories": container(request).categories.list_active()
        }
    )

@router.post("/incidents/new")
def create(
    request: Request,
    user=employee,
    title: str = Form(),
    description: str = Form(),
    category: str = Form(),
    service_id: str = Form(),
    impact: int = Form(),
    urgency: int = Form(),
    affected_users: int = Form(1)
):
    inc = container(request).incident_service.create_incident(
        user, title, description, category, service_id, impact, urgency, affected_users
    )
    return RedirectResponse(f"/employee/incidents/{inc.id}", 303)

@router.get("/incidents/{incident_id}")
def detail(
    request: Request,
    incident_id: str,
    user=Depends(require_permission(Perm.INCIDENT_VIEW_OWN, Perm.INCIDENT_VIEW_ALL))
):
    c = container(request)
    incident = c.incident_service.get_incident(user, incident_id)
    history = c.audit.list_for_incident(incident_id)
    comments = c.collab.list_comments(user, incident_id)
    feedback = c.feedback.get(incident_id)
    reporter = c.users.get(incident.reporter_id)
    assignee = c.users.get(incident.assigned_to) if incident.assigned_to else None
    service = c.services.get(incident.service_id)
    summary = c.advisor.summarize(incident)
    return templates.TemplateResponse(
        request, "incident_detail.html",
        {
            "user": user,
            "incident": incident,
            "reporter": reporter,
            "assignee": assignee,
            "service": service,
            "history": history,
            "comments": comments,
            "feedback": feedback,
            "error": request.query_params.get("error"),
            "summary": summary,
        }
    )

@router.post("/incidents/{incident_id}/reply")
def reply(request: Request, incident_id: str, user=employee, answer: str = Form()):
    container(request).collab.reply(user, incident_id, answer)
    return RedirectResponse(f"/employee/incidents/{incident_id}?msg=Information+provided+to+technician", 303)

@router.post("/incidents/{incident_id}/verify")
def verify(request: Request, incident_id: str, user=employee):
    try:
        container(request).incident_service.verify(user, incident_id)
        return RedirectResponse(f"/employee/incidents/{incident_id}?msg=Resolution+confirmed+successfully.+Please+rate+the+service+below.", 303)
    except ItsmError as e:
        return RedirectResponse(f"/employee/incidents/{incident_id}?error={quote_plus(str(e))}", 303)

@router.post("/incidents/{incident_id}/close")
def close(request: Request, incident_id: str, user=employee):
    c = container(request)
    try:
        c.incident_service.close(user, incident_id)
        return RedirectResponse(f"/employee/incidents/{incident_id}?msg=Incident+closed+successfully", 303)
    except ItsmError as e:
        return RedirectResponse(f"/employee/incidents/{incident_id}?error={quote_plus(str(e))}", 303)

@router.post("/incidents/{incident_id}/reject")
def reject(request: Request, incident_id: str, user=employee, reason: str = Form("")):
    c = container(request)
    try:
        c.incident_service.reject_resolution(user, incident_id, reason)
        return RedirectResponse(f"/employee/incidents/{incident_id}?msg=Resolution+rejected.+Investigation+reopened.", 303)
    except ItsmError as e:
        return RedirectResponse(f"/employee/incidents/{incident_id}?error={quote_plus(str(e))}", 303)

@router.post("/incidents/{incident_id}/feedback")
def submit_feedback(
    request: Request,
    incident_id: str,
    user=employee,
    rating: int = Form(),
    comment: str = Form("")
):
    container(request).collab.submit_feedback(user, incident_id, rating, comment)
    return RedirectResponse(f"/employee/incidents/{incident_id}?msg=Thank+you+for+your+feedback!", 303)
