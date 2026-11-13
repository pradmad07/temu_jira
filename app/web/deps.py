from pathlib import Path
from fastapi import Request
from fastapi.templating import Jinja2Templates
from app.domain.exceptions import AuthenticationError, AuthorizationError

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
def container(request: Request): return request.app.state.container

def _current_user(request: Request):
    uid = request.session.get("user_id")
    user = container(request).users.get(uid) if uid else None
    if user is None or not user.active: raise AuthenticationError("Please log in")   # disabled accounts lose access at once
    return user

def require_permission(*perms):
    """FastAPI dependency: logged-in user who holds at least one of `perms`. Backend is authoritative; hiding buttons is not security."""
    def dep(request: Request):
        user = _current_user(request)
        if not any(user.can(p) for p in perms): raise AuthorizationError("You are not allowed to do that")
        return user
    return dep
