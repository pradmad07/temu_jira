"""SQLite implementations (stdlib sqlite3 - think JDBC). Owner: Kevalin; Gaurav fills in search()."""
import sqlite3
from datetime import datetime
from pathlib import Path
from app.domain.enums import Role, Status, Priority, Category
from app.domain.exceptions import PersistenceError
from app.domain.models import User, Technician, Incident, AuditRecord, Service, SlaPolicy
from .interfaces import *

SCHEMA = Path(__file__).resolve().parents[2] / "schema.sql"

class Database:
    def __init__(self, path=":memory:"):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON")
    def init_schema(self): self._conn.executescript(SCHEMA.read_text())
    def execute(self, sql, params=()):
        # TODO: commit-per-statement is fine for now; add a transaction() context manager so
        # incident + audit saves commit together (rubric: "database failure" handling).
        try:
            cur = self._conn.execute(sql, params); self._conn.commit(); return cur
        except sqlite3.Error as e: raise PersistenceError(f"Database error: {e}") from e
    def query(self, sql, params=()):
        try: return self._conn.execute(sql, params).fetchall()
        except sqlite3.Error as e: raise PersistenceError(f"Database error: {e}") from e

def _user(r) -> User:
    if r["role"] == Role.TECHNICIAN.value:
        return Technician(r["name"], r["email"], r["password_hash"], [s for s in r["skills"].split(",") if s],
                          r["experience_years"], bool(r["available"]), r["max_workload"], id=r["id"])
    return User(r["name"], r["email"], r["password_hash"], Role(r["role"]), id=r["id"])

class SqliteUserRepository(UserRepository):
    def __init__(self, db: Database): self._db = db
    def add(self, u):
        t = isinstance(u, Technician)
        self._db.execute("INSERT INTO users(id,name,email,password_hash,role,skills,experience_years,available,max_workload) VALUES(?,?,?,?,?,?,?,?,?)",
            (u.id, u.name, u.email, u.password_hash, u.role.value, ",".join(sorted(u.skills)) if t else "",
             u.experience_years if t else 0, int(u.available) if t else 1, u.max_workload if t else 5))
    def get(self, user_id):
        rows = self._db.query("SELECT * FROM users WHERE id=?", (user_id,)); return _user(rows[0]) if rows else None
    def get_by_email(self, email):
        rows = self._db.query("SELECT * FROM users WHERE email=?", (email.lower(),)); return _user(rows[0]) if rows else None
    def list_technicians(self):
        return [_user(r) for r in self._db.query("SELECT * FROM users WHERE role=?", (Role.TECHNICIAN.value,))]

def _incident(r) -> Incident:
    return Incident(r["reporter_id"], r["title"], r["description"], Category(r["category"]), r["service_id"],
                    r["impact"], r["urgency"], r["affected_users"], id=r["id"], status=Status(r["status"]),
                    priority=Priority[r["priority"]] if r["priority"] else None, assigned_to=r["assigned_to"],
                    created_at=datetime.fromisoformat(r["created_at"]), resolution=r["resolution"])

class SqliteIncidentRepository(IncidentRepository):
    def __init__(self, db: Database): self._db = db
    def save(self, i):
        self._db.execute("INSERT OR REPLACE INTO incidents(id,reporter_id,title,description,category,service_id,impact,urgency,affected_users,priority,status,assigned_to,created_at,resolution) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (i.id, i.reporter_id, i.title, i.description, i.category.value, i.service_id, i.impact, i.urgency,
             i.affected_users, i.priority.name if i.priority else None, i.status.value, i.assigned_to,
             i.created_at.isoformat(), i.resolution))
    def get(self, incident_id):
        rows = self._db.query("SELECT * FROM incidents WHERE id=?", (incident_id,)); return _incident(rows[0]) if rows else None
    def list_by_reporter(self, user_id):
        return [_incident(r) for r in self._db.query("SELECT * FROM incidents WHERE reporter_id=? ORDER BY created_at DESC", (user_id,))]
    def count_active_by_technician(self, technician_id):
        active = (Status.ASSIGNED.value, Status.ACKNOWLEDGED.value, Status.IN_PROGRESS.value)
        return self._db.query("SELECT COUNT(*) c FROM incidents WHERE assigned_to=? AND status IN (?,?,?)", (technician_id, *active))[0]["c"]
    def search(self, **filters):
        raise NotImplementedError("TODO(Gaurav): build WHERE clause from filters; >=5 filters + pagination")

class SqliteAuditRepository(AuditRepository):
    def __init__(self, db: Database): self._db = db
    def append(self, a):
        self._db.execute("INSERT INTO audit_records(incident_id,actor_id,action,old_status,new_status,description,timestamp) VALUES(?,?,?,?,?,?,?)",
            (a.incident_id, a.actor_id, a.action, a.old_status, a.new_status, a.description, a.timestamp.isoformat()))
    def list_for_incident(self, incident_id):
        return [AuditRecord(r["incident_id"], r["actor_id"], r["action"], r["old_status"], r["new_status"], r["description"],
                datetime.fromisoformat(r["timestamp"])) for r in self._db.query("SELECT * FROM audit_records WHERE incident_id=? ORDER BY id", (incident_id,))]

class SqliteServiceRepository(ServiceRepository):
    def __init__(self, db: Database): self._db = db
    def get(self, service_id):
        rows = self._db.query("SELECT * FROM services WHERE id=?", (service_id,))
        return Service(rows[0]["id"], rows[0]["name"], rows[0]["criticality"]) if rows else None
    def list_all(self): return [Service(r["id"], r["name"], r["criticality"]) for r in self._db.query("SELECT * FROM services ORDER BY name")]

class SqliteSlaPolicyRepository(SlaPolicyRepository):
    def __init__(self, db: Database): self._db = db
    def get_for_priority(self, priority):
        rows = self._db.query("SELECT * FROM sla_policies WHERE priority=?", (priority.name,))
        return SlaPolicy(priority, rows[0]["response_minutes"], rows[0]["resolution_minutes"]) if rows else None
