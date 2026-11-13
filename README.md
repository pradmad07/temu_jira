# I-ITSM (Intelligent IT Service Management) - OOP project

## Run it
```
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest                                   # stubs owned by teammates fail on purpose; goal = all green
uvicorn app.main:app --reload            # http://127.0.0.1:8000
```
Demo logins (password `password123`): e1@itsm.local (employee), t1@itsm.local (technician), lead@itsm.local (team lead),
admin@itsm.local, mgr@itsm.local (IT manager). **Delete `itsm.db` whenever `schema.sql` changes** (there are no migrations).

Environment variables: `SECRET_KEY` (session signing, set it outside development), `ITSM_DB` (database file),
`ITSM_SCAN_SECONDS` (SLA scan interval, default 30, 0 = off), `ITSM_HTTPS=1` (secure cookies + HSTS when served over HTTPS), `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REDIRECT_URI` (Google sign-in, optional), `ITSM_SSO_DOMAINS` (comma-separated allowed email domains for SSO).
HTTPS and SSO setup: docs/SSO_AND_HTTPS.md.

Read in this order: docs/DESIGN.md -> docs/PLAN.md (owners, schedule) -> app/services/incident_service.py. Also docs/SECURITY.md.
