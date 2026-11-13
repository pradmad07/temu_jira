# Security considerations (brief asks us to document these)
| Requirement | What we do | Where |
|---|---|---|
| Authentication | Email + password login; generic error for wrong user or password; disabled accounts cannot log in and lose their session at once | `AuthService`, `web/deps.py` |
| Password protection | PBKDF2-HMAC-SHA256, 600,000 iterations, random 16-byte salt per user, work factor stored inside each hash and upgraded at next login, constant-time compare, min. 8 characters; never stored or logged in clear. Unknown emails cost the same time as wrong passwords | `AuthService` |
| Single sign-on (optional) | Google OpenID Connect via Authlib. Email must be verified by Google; optional approved-domain list; SSO never creates or changes anything above EMPLOYEE; disabled accounts stay locked out; client secret from environment | `routes_sso.py`, `AuthService.login_with_identity` |
| Transport security | HTTPS is deployment configuration with a documented path; with `ITSM_HTTPS=1` the cookie is `Secure` and HSTS is sent. Security headers (nosniff, frame deny, referrer policy) are always sent | `main.py`, docs/SSO_AND_HTTPS.md |
| Role-based authorization | Permission map; routes use `require_permission`, services re-check (`actor.can`, ownership, assignee). Hiding a button is not security | `permissions.py`, `deps.py`, services |
| Unauthorized operations | `AuthorizationError` -> HTTP 403; tests cover wrong technician, wrong reporter, employee admin actions | `tests/` |
| Input validation | Domain objects validate on construction; FastAPI typed forms; friendly 400 page for bad input; category names regex-checked | `models.py`, `main.py` |
| Secure session | Signed cookie, `SameSite=Lax` (blocks cross-site POST), optional `Secure` flag via `ITSM_HTTPS=1`, fresh session on login | `main.py`, `routes_auth.py` |
| Secrets | `SECRET_KEY` and any API key come from environment variables, never from Git; a warning is logged if the dev key is in use | `main.py` |
| SQL injection | Parameterised queries only | `sqlite_repos.py` |
| XSS | Jinja2 auto-escaping of template output; error pages use `html.escape`. Manual check: report an incident titled `<script>alert(1)</script>` and confirm it shows as text | templates |
| Audit | Every incident action and every admin/config change is recorded with actor and timestamp | `AuditObserver` |

**Not implemented (state this in the report):** CSRF tokens (SameSite mitigates the common case), login rate-limiting/lockout, password reset, MFA, HTTPS certificates themselves (deployment, see docs/SSO_AND_HTTPS.md), encryption of the database file, audit of failed logins.
