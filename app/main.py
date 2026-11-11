import html, os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware
from app.container import build_container
from app.seed import seed
from app.domain.exceptions import *
from app.web import routes_auth, routes_employee, routes_technician, routes_admin

app = FastAPI(title="I-ITSM")
app.add_middleware(SessionMiddleware, secret_key=os.environ.get("SECRET_KEY", "dev-only-change-me"))
app.state.container = build_container(os.environ.get("ITSM_DB", "itsm.db"))
if app.state.container.users.get_by_email("admin@itsm.local") is None: seed(app.state.container)
for r in (routes_auth, routes_employee, routes_technician, routes_admin): app.include_router(r.router)

_STATUS = [(AuthorizationError, 403), (NotFoundError, 404), (InvalidTransitionError, 409), (PersistenceError, 503)]

@app.exception_handler(ItsmError)
async def itsm_error(request: Request, exc: ItsmError):
    if isinstance(exc, AuthenticationError): return RedirectResponse("/login", 303)
    code = next((c for t, c in _STATUS if isinstance(exc, t)), 400)
    return HTMLResponse(f"<h3>{html.escape(str(exc))}</h3><a href='javascript:history.back()'>Go back</a>", status_code=code)
