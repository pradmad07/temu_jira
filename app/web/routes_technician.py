"""Technician pages (owner: Pradhyumn). TODO: inbox of assigned incidents + workload, acknowledge/start/notes/request info/resolve."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from app.domain.permissions import Perm
from .deps import require_permission

router = APIRouter(prefix="/technician")

@router.get("")
def home(request: Request, user=Depends(require_permission(Perm.INCIDENT_VIEW_ASSIGNED))):
    return HTMLResponse("<h3>Technician dashboard - TODO(Pradhyumn)</h3><a href='/logout'>Log out</a>")
