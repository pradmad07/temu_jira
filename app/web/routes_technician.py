"""Technician inbox and incident work actions."""
from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app.domain.filters import IncidentFilter
from app.domain.permissions import Perm
from app.services.assignment import strategy_by_name
from app.services.duplicates import DuplicateDetector
from .deps import container, require_permission, templates

router = APIRouter(prefix="/technician")
technician = Depends(require_permission(Perm.INCIDENT_VIEW_ASSIGNED))
work = Depends(require_permission(Perm.INCIDENT_WORK))


@router.get("")
def home(request: Request, user=technician):
    c = container(request)
    incidents = c.incident_service.list_for(user)
    feedbacks = {inc.id: c.feedback.get(inc.id) for inc in incidents}
    reporters = {u.id: u for u in c.users.list_all()}
    return templates.TemplateResponse(
        request,
        "technician_home.html",
        {
            "user": user,
            "incidents": incidents,
            "reporters": reporters,
            "active_count": c.incidents.count_active_by_technician(user.id),
            "max_workload": getattr(user, "max_workload", None),
            "feedbacks": feedbacks,
        },
    )


@router.get("/incidents/{incident_id}")
def detail(request: Request, incident_id: str, user=technician):
    c = container(request)
    incident = c.incident_service.get_incident(user, incident_id)
    recent = c.incidents.search(IncidentFilter(service_id=incident.service_id), limit=50)
    duplicates = DuplicateDetector().find_candidates(incident, recent)
    strategy = strategy_by_name(c.config.get("assignment_strategy", "skill"))
    candidates = c.users.list_technicians()
    workloads = {candidate.id: c.incidents.count_active_by_technician(candidate.id) for candidate in candidates}
    feedback = c.feedback.get(incident_id)
    reporter = c.users.get(incident.reporter_id)
    assignee = c.users.get(incident.assigned_to) if incident.assigned_to else None
    service = c.services.get(incident.service_id)
    summary = c.advisor.summarize(incident)
    resolution_suggestions = c.advisor.suggest_resolutions(incident)
    return templates.TemplateResponse(
        request,
        "technician_detail.html",
        {
            "user": user,
            "incident": incident,
            "reporter": reporter,
            "assignee": assignee,
            "service": service,
            "history": c.audit.list_for_incident(incident_id),
            "comments": c.collab.list_comments(user, incident_id),
            "duplicates": duplicates,
            "recommendations": strategy.recommend(incident, candidates, workloads),
            "feedback": feedback,
            "summary": summary,
            "resolution_suggestions": resolution_suggestions,
        },
    )


def _redirect(incident_id: str):
    return RedirectResponse(f"/technician/incidents/{incident_id}", status_code=303)


@router.post("/incidents/{incident_id}/acknowledge")
def acknowledge(request: Request, incident_id: str, user=work):
    container(request).incident_service.acknowledge(user, incident_id)
    return _redirect(incident_id)


@router.post("/incidents/{incident_id}/start")
def start(request: Request, incident_id: str, user=work):
    container(request).incident_service.start_investigation(user, incident_id)
    return _redirect(incident_id)


@router.post("/incidents/{incident_id}/note")
def add_note(request: Request, incident_id: str, text: str = Form(), user=work):
    container(request).collab.add_note(user, incident_id, text)
    return _redirect(incident_id)


@router.post("/incidents/{incident_id}/request-info")
def request_info(request: Request, incident_id: str, question: str = Form(), user=work):
    container(request).collab.request_info(user, incident_id, question)
    return _redirect(incident_id)


@router.post("/incidents/{incident_id}/resolve")
def resolve(request: Request, incident_id: str, resolution: str = Form(), user=work):
    container(request).incident_service.resolve(user, incident_id, resolution)
    return _redirect(incident_id)
