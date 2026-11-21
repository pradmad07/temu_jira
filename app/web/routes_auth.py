from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from app.domain.exceptions import ItsmError
from app.domain.permissions import Perm
from .deps import templates, container

router = APIRouter()

def home_for(user):   # role-agnostic: decided by permissions, so new roles need no change here
    if user.can(Perm.INCIDENT_VIEW_ALL): return "/admin"
    if user.can(Perm.INCIDENT_VIEW_ASSIGNED): return "/technician"
    return "/employee/incidents"

def _login_page(request: Request, error=None, status=200, section="login"):
    ctx = {"user": None, "sso": getattr(request.app.state, "sso_providers", [])}
    if error:
        ctx["error"] = error
        ctx["error_section"] = section
    return templates.TemplateResponse(request, "login.html", ctx, status_code=status)

@router.get("/")
def root(request: Request):
    uid = request.session.get("user_id"); user = container(request).users.get(uid) if uid else None
    return RedirectResponse(home_for(user) if user else "/login", 303)

@router.get("/login")
def login_page(request: Request): return _login_page(request)

@router.post("/login")
def login(request: Request, email: str = Form(), password: str = Form()):
    try: user = container(request).auth.login(email, password)
    except ItsmError as e: return _login_page(request, str(e), 401)
    request.session.clear(); request.session["user_id"] = user.id   # fresh session on login (no session fixation)
    return RedirectResponse(home_for(user), 303)

@router.post("/register")
def register(request: Request, name: str = Form(), email: str = Form(),
             password: str = Form(), confirm_password: str = Form("")):
    if password != confirm_password:
        return _login_page(request, "Passwords do not match", 400, section="register")
    try: user = container(request).auth.register(name, email, password)
    except ItsmError as e: return _login_page(request, str(e), 400, section="register")
    request.session.clear(); request.session["user_id"] = user.id
    return RedirectResponse(home_for(user), 303)

@router.get("/logout")
def logout(request: Request): request.session.clear(); return RedirectResponse("/login", 303)

@router.get("/notifications")
def notifications_page(request: Request):
    uid = request.session.get("user_id")
    if not uid: return RedirectResponse("/login", 303)
    user = container(request).users.get(uid)
    if not user: return RedirectResponse("/login", 303)
    notes = container(request).notifications.list_for_recipient(user.id)
    return templates.TemplateResponse(request, "notifications.html", {"user": user, "notifications": notes})

@router.post("/notifications/{notification_id}/read")
def mark_notification_read(request: Request, notification_id: int):
    uid = request.session.get("user_id")
    if not uid: return RedirectResponse("/login", 303)
    container(request).notifications.mark_read(notification_id)
    return RedirectResponse("/notifications", 303)

@router.post("/notifications/read-all")
def mark_all_notifications_read(request: Request):
    uid = request.session.get("user_id")
    if not uid: return RedirectResponse("/login", 303)
    container(request).notifications.mark_all_read(uid)
    return RedirectResponse("/notifications?msg=All+notifications+marked+as+read", 303)

