# I-ITSM (Intelligent IT Service Management) - OOP project

## Run it
```
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pytest                                   # 9 pass, 11 fail on purpose (stubs); goal = all green
uvicorn app.main:app --reload            # http://127.0.0.1:8000
```
Demo logins (password `password123`): e1@itsm.local (employee), t1@itsm.local (technician), admin@itsm.local.
Delete `itsm.db` to reset the data. Full plan, owners and schedule: **docs/PLAN.md**.
