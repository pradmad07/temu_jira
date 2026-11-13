# Google sign-in (SSO) and the path to HTTPS

## Part 1: Google sign-in
**What it is.** OpenID Connect, built on OAuth2. The user logs in on Google's own page; Google then tells our app who they are (email, name, and whether Google has verified the email). Our app never sees a Google password.

**The flow.** Click "Sign in with Google" -> `/login/google` redirects to Google with a random anti-forgery `state` -> user authenticates -> Google redirects to `/auth/google/callback` -> Authlib checks `state` and exchanges the code for tokens -> `AuthService.login_with_identity()` decides who this is -> we start the normal session cookie. After that, SSO users and password users are identical.

**Rules we enforce** (all in `login_with_identity`, all tested): the email must be verified by Google; optionally only approved domains (`ITSM_SSO_DOMAINS=company.com`); an existing technician/admin logs in as themselves; an unknown email becomes an EMPLOYEE, never anything higher (roles stay under admin control); disabled accounts stay locked out; SSO-only accounts get a random password nobody knows.

**Setup (labels in Google's console change over time; check their current docs)**
1. Google Cloud Console -> create a project -> configure the OAuth consent screen (while in "testing" mode, add your team's Google accounts as test users).
2. Credentials -> Create credentials -> OAuth client ID -> type "Web application".
3. Authorised redirect URI: `http://localhost:8000/auth/google/callback`.
4. Set environment variables, then `pip install -r requirements.txt` and start the app:
```
export GOOGLE_CLIENT_ID=...      # Windows PowerShell: $env:GOOGLE_CLIENT_ID="..."
export GOOGLE_CLIENT_SECRET=...
export SECRET_KEY=<long random string>
uvicorn app.main:app --reload
```
5. Open **http://localhost:8000** (not 127.0.0.1). Use the same host name the whole time: the session cookie belongs to one host, and a mismatch causes a "state" error.
If the variables are not set, the button simply does not appear and nothing else changes. Never commit the secret; if it leaks, rotate it in the console.

**Microsoft (not implemented; same pattern).** Register an app in Microsoft Entra ID, add a redirect URI, register a second provider in Authlib with Microsoft's OpenID metadata URL, and map the claims. Caution: Microsoft's `email` claim is not guaranteed to be verified for accounts from other tenants, so only trust it if the app is single-tenant (your own organisation). Check Microsoft's docs for the exact URLs.

## Part 2: HTTPS
**Why.** Without TLS, passwords, session cookies and Google's redirect travel readable on the network. Google also requires HTTPS redirect URIs for anything other than localhost.

**What the app already does when `ITSM_HTTPS=1`:** session cookie gets the `Secure` flag (browser never sends it over plain HTTP), `Strict-Transport-Security` is sent (browser refuses plain HTTP afterwards). Always sent: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`. The app does not manage certificates itself; that is deliberately the job of whatever sits in front of it.

**Option A: HTTPS on your own laptop (good for the recorded demo).** Install `mkcert` (a tool that makes locally trusted certificates), then:
```
mkcert -install
mkcert localhost                         # prints the two .pem files it created
ITSM_HTTPS=1 uvicorn app.main:app --ssl-keyfile localhost-key.pem --ssl-certfile localhost.pem
```
Open https://localhost:8000 and use `https://localhost:8000/auth/google/callback` as the redirect URI. (Do not commit the .pem files.)

**Option B: a hosting platform.** Platforms that deploy from Git typically give you an HTTPS URL and terminate TLS for you (check the current free-tier terms). Set the environment variables there (`SECRET_KEY`, `ITSM_HTTPS=1`, `GOOGLE_*`, `GOOGLE_REDIRECT_URI=https://<your-url>/auth/google/callback`) and start with:
```
uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips="*"
```
`--proxy-headers` makes the app believe the proxy's "this request was HTTPS" header. Use `"*"` only when the app is reachable through the platform's proxy and nothing else. SQLite on platforms with temporary disks loses data on restart; use a persistent disk or move to Postgres (see DESIGN.md scaling).

**Option C: your own server.** Put a reverse proxy in front and keep uvicorn on loopback (`--host 127.0.0.1 --proxy-headers`). With Caddy, a public domain name is enough for automatic Let's Encrypt certificates:
```
itsm.example.com {
    reverse_proxy 127.0.0.1:8000
}
```
(Caddy also redirects HTTP to HTTPS by default. With nginx, use certbot and add a redirect from port 80.)

**Report checklist.** TLS ends at the proxy; the hop to uvicorn is on the same machine. `ITSM_HTTPS=1`; HTTP -> HTTPS redirect at the proxy; HSTS sent; `SECRET_KEY` and OAuth secrets only in environment variables; redirect URI uses https. HTTPS protects data in transit only; it does not replace login throttling, input validation or authorisation checks.
