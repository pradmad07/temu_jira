import html, logging, os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from app.container import build_container
from app.seed import seed
from app.domain.exceptions import *
from app.services.scheduler import PeriodicTask
from app.web import routes_auth, routes_employee, routes_technician, routes_admin

SECRET = os.environ.get("SECRET_KEY", "dev-only-change-me")
if SECRET == "dev-only-change-me": logging.warning("SECRET_KEY not set: using the insecure development key. Set it before any real deployment.")

@asynccontextmanager
async def lifespan(app: FastAPI):
    secs = int(os.environ.get("ITSM_SCAN_SECONDS", "30"))       # 0 disables the background SLA scan
    task = PeriodicTask(app.state.container.sla.scan, secs, "sla-scan") if secs > 0 else None
    if task: task.start()
    yield
    if task: task.stop()

app = FastAPI(title="I-ITSM", lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=SECRET, same_site="lax", https_only=os.environ.get("ITSM_HTTPS") == "1")
app.state.container = build_container(os.environ.get("ITSM_DB", "itsm.db"))
if app.state.container.users.get_by_email("admin@itsm.local") is None: seed(app.state.container)
for r in (routes_auth, routes_employee, routes_technician, routes_admin): app.include_router(r.router)

_STATUS = [(AuthorizationError, 403), (NotFoundError, 404), (InvalidTransitionError, 409), (TechnicianUnavailableError, 409),
           (DuplicateIncidentError, 409), (ExternalServiceError, 502), (MissingSlaError, 500), (PersistenceError, 503)]
def _page(message, code): return HTMLResponse(f"<h3>{html.escape(str(message))}</h3><a href='javascript:history.back()'>Go back</a>", status_code=code)

@app.exception_handler(ItsmError)
async def itsm_error(request: Request, exc: ItsmError):
    if isinstance(exc, AuthenticationError): return RedirectResponse("/login", 303)
    return _page(exc, next((c for t, c in _STATUS if isinstance(exc, t)), 400))

@app.exception_handler(RequestValidationError)   # e.g. text typed into a number field: friendly page, not raw JSON
async def bad_input(request: Request, exc: RequestValidationError): return _page("Some of the information you entered is not valid.", 400)
