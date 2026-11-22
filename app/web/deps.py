from pathlib import Path
from datetime import datetime, timezone, timedelta
from fastapi import Request
from fastapi.templating import Jinja2Templates
from app.domain.exceptions import AuthenticationError, AuthorizationError
import logging

IST = timezone(timedelta(hours=5, minutes=30), "IST")

def format_ist(dt, fmt=None):
    if not dt:
        return "-"
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt)
        except Exception:
            return dt
    if getattr(dt, "tzinfo", None) is None:
        dt = dt.replace(tzinfo=timezone.utc)
    ist_dt = dt.astimezone(IST)
    if fmt:
        return ist_dt.strftime(fmt)
    return ist_dt.strftime("%d %b %H:%M") + " IST"

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))
templates.env.filters["ist"] = format_ist
templates.env.globals["format_ist"] = format_ist
templates.env.globals["IST"] = IST

def get_unread_count(request: Request, user_id: str) -> int:
    try:
        c = container(request)
        if hasattr(c, "notifications"):
            return c.notifications.count_unread(user_id, channel="IN_APP")
    except Exception:
        logging.exception("Failed to count unread notifications for user %s", user_id)
    return 0

templates.env.globals["unread_count_for"] = get_unread_count
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
