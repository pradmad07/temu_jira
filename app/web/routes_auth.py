from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from app.domain.permissions import Perm
from app.domain.exceptions import ItsmError
from .deps import templates, container

router = APIRouter()
def home_for(user):   # role-agnostic: decided by permissions, so new roles need no change here
    if user.can(Perm.INCIDENT_VIEW_ALL): return "/admin"
    if user.can(Perm.INCIDENT_VIEW_ASSIGNED): return "/technician"
    return "/employee/incidents"

@router.get("/")
def root(request: Request):
    uid = request.session.get("user_id"); user = container(request).users.get(uid) if uid else None
    return RedirectResponse(home_for(user) if user else "/login", 303)

@router.get("/login")
def login_page(request: Request): return templates.TemplateResponse(request, "login.html", {"user": None})

@router.post("/login")
def login(request: Request, email: str = Form(), password: str = Form()):
    try: user = container(request).auth.login(email, password)
    except ItsmError as e: return templates.TemplateResponse(request, "login.html", {"user": None, "error": str(e)}, status_code=401)
    request.session.clear(); request.session["user_id"] = user.id   # fresh session on login (no session fixation)
    return RedirectResponse(home_for(user), 303)

@router.post("/register")
def register(request: Request, name: str = Form(), email: str = Form(), password: str = Form()):
    try: user = container(request).auth.register(name, email, password)
    except ItsmError as e: return templates.TemplateResponse(request, "login.html", {"user": None, "error": str(e)}, status_code=400)
    request.session["user_id"] = user.id
    return RedirectResponse(home_for(user), 303)

@router.get("/logout")
def logout(request: Request): request.session.clear(); return RedirectResponse("/login", 303)
