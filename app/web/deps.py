from pathlib import Path
from fastapi import Request
from fastapi.templating import Jinja2Templates
from app.domain.exceptions import AuthenticationError, AuthorizationError

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
def container(request: Request): return request.app.state.container

def require_role(*roles):
    """FastAPI dependency: returns the logged-in user or raises. Backend is authoritative; hiding buttons is not security."""
    def dep(request: Request):
        uid = request.session.get("user_id")
        user = container(request).users.get(uid) if uid else None
        if user is None: raise AuthenticationError("Please log in")
        if user.role not in roles: raise AuthorizationError("You are not allowed to do that")
        return user
    return dep
