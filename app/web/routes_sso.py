"""Optional Google sign-in via OpenID Connect (Authlib). Active only when GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET are set;
otherwise nothing is registered and the app behaves exactly as before. The id/secret come from the environment, never from Git."""
import logging, os
from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from app.domain.exceptions import ItsmError
from .deps import container, templates
from .routes_auth import home_for

def build_router():
    client_id, client_secret = os.environ.get("GOOGLE_CLIENT_ID"), os.environ.get("GOOGLE_CLIENT_SECRET")
    if not (client_id and client_secret): return None
    from authlib.integrations.starlette_client import OAuth     # imported only when SSO is configured
    oauth = OAuth()
    oauth.register(name="google", client_id=client_id, client_secret=client_secret,
                   server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
                   client_kwargs={"scope": "openid email profile"})
    router = APIRouter()

    def _fail(request, message):
        return templates.TemplateResponse(request, "login.html", {"user": None, "error": message, "sso": ["google"]}, status_code=401)

    @router.get("/login/google")
    async def login_google(request: Request):
        # GOOGLE_REDIRECT_URI overrides the generated URL (needed behind an HTTPS proxy). Must match the Google console exactly.
        redirect_uri = os.environ.get("GOOGLE_REDIRECT_URI") or str(request.url_for("google_callback"))
        return await oauth.google.authorize_redirect(request, redirect_uri)

    @router.get("/auth/google/callback", name="google_callback")
    async def google_callback(request: Request):
        try:
            token = await oauth.google.authorize_access_token(request)       # also checks the anti-forgery `state`
            info = token.get("userinfo") or {}
            user = container(request).auth.login_with_identity(info.get("email"), info.get("name"), bool(info.get("email_verified")))
        except ItsmError as e: return _fail(request, str(e))
        except Exception:
            logging.exception("Google sign-in failed"); return _fail(request, "Google sign-in failed. Please try again.")
        request.session.clear(); request.session["user_id"] = user.id
        return RedirectResponse(home_for(user), 303)
    return router
