"""Admin pages (owner: Gaurav). TODO: filterable incident table, reports, audit log, manage users/services/SLA/strategy, 'run SLA scan'."""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from app.domain.enums import Role
from .deps import require_role

router = APIRouter(prefix="/admin")

@router.get("")
def home(request: Request, user=Depends(require_role(Role.ADMIN))):
    return HTMLResponse("<h3>Admin dashboard - TODO(Gaurav)</h3><a href='/logout'>Log out</a>")
