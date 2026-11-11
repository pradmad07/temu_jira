"""Technician pages (owner: Pradhyumn). TODO: inbox of assigned incidents + workload, acknowledge/start/notes/request info/resolve."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from app.domain.enums import Role
from .deps import require_role

router = APIRouter(prefix="/technician")

@router.get("")
def home(request: Request, user=Depends(require_role(Role.TECHNICIAN))):
    return HTMLResponse("<h3>Technician dashboard - TODO(Pradhyumn)</h3><a href='/logout'>Log out</a>")
