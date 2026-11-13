"""SQLite implementations (stdlib sqlite3 - think JDBC). Owner: Kevalin; Gaurav fills in search()."""
import sqlite3, threading
from datetime import datetime
from pathlib import Path
from app.domain.enums import Role, Status, Priority
from app.domain.exceptions import PersistenceError
from app.domain.factories import UserFactory
from app.domain.models import (User, Technician, Incident, AuditRecord, Service, SlaPolicy, SlaDeadlines, Comment,
                               Feedback, normalise_category)
from .interfaces import *

SCHEMA = Path(__file__).resolve().parents[2] / "schema.sql"
def _dt(v): return datetime.fromisoformat(v) if v else None
def _iso(v): return v.isoformat() if v else None

class Database:
    """One shared connection guarded by a lock: web threads and the background SLA thread all use it."""
    def __init__(self, path=":memory:"):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._lock = threading.RLock()
    def init_schema(self):
        with self._lock: self._conn.executescript(SCHEMA.read_text())
    def execute(self, sql, params=()):
        # Known limit: commit-per-statement. A UnitOfWork (one commit per use case) is the scaling path - docs/DESIGN.md.
        with self._lock:
            try:
                cur = self._conn.execute(sql, params); self._conn.commit(); return cur
            except sqlite3.Error as e: raise PersistenceError(f"Database error: {e}") from e
    def query(self, sql, params=()):
        with self._lock:
            try: return self._conn.execute(sql, params).fetchall()
            except sqlite3.Error as e: raise PersistenceError(f"Database error: {e}") from e

def _user(r) -> User:
    tech = {}
    if r["role"] == Role.TECHNICIAN.value:
        tech = dict(skills=[s for s in r["skills"].split(",") if s], experience_years=r["experience_years"],
                    available=bool(r["available"]), max_workload=r["max_workload"])
    return UserFactory.create(Role(r["role"]), r["name"], r["email"], r["password_hash"], id=r["id"],
                              reports_to=r["reports_to"], active=bool(r["active"]), **tech)

class SqliteUserRepository(UserRepository):
    def __init__(self, db: Database): self._db = db
    def add(self, u):
        t = isinstance(u, Technician)
        self._db.execute("INSERT INTO users(id,name,email,password_hash,role,skills,experience_years,available,max_workload,reports_to,active) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (u.id, u.name, u.email, u.password_hash, u.role.value, ",".join(sorted(u.skills)) if t else "",
             u.experience_years if t else 0, int(u.available) if t else 1, u.max_workload if t else 5, u.reports_to, int(u.active)))
    def get(self, user_id):
        rows = self._db.query("SELECT * FROM users WHERE id=?", (user_id,)); return _user(rows[0]) if rows else None
    def get_by_email(self, email):
        rows = self._db.query("SELECT * FROM users WHERE email=?", (email.lower(),)); return _user(rows[0]) if rows else None
    def list_technicians(self):
        return [_user(r) for r in self._db.query("SELECT * FROM users WHERE role=? AND active=1", (Role.TECHNICIAN.value,))]
    def list_all(self): return [_user(r) for r in self._db.query("SELECT * FROM users ORDER BY name")]
    def set_active(self, user_id, active): self._db.execute("UPDATE users SET active=? WHERE id=?", (int(active), user_id))

_INC_COLS = ("id,reporter_id,title,description,category,service_id,impact,urgency,affected_users,priority,status,assigned_to,"
             "created_at,resolution,acknowledged_at,resolved_at,closed_at,response_due,resolution_due")
_OPEN = (Status.NEW, Status.CLASSIFIED, Status.ASSIGNED, Status.ACKNOWLEDGED, Status.IN_PROGRESS)

def _incident(r) -> Incident:
    sla = SlaDeadlines(_dt(r["response_due"]), _dt(r["resolution_due"])) if r["response_due"] else None
    return Incident(r["reporter_id"], r["title"], r["description"], r["category"], r["service_id"], r["impact"], r["urgency"],
                    r["affected_users"], id=r["id"], status=Status(r["status"]),
                    priority=Priority[r["priority"]] if r["priority"] else None, assigned_to=r["assigned_to"],
                    created_at=_dt(r["created_at"]), resolution=r["resolution"], acknowledged_at=_dt(r["acknowledged_at"]),
                    resolved_at=_dt(r["resolved_at"]), closed_at=_dt(r["closed_at"]), sla=sla)

class SqliteIncidentRepository(IncidentRepository):
    def __init__(self, db: Database): self._db = db
    def save(self, i):
        sla = i.sla
        self._db.execute(f"INSERT OR REPLACE INTO incidents({_INC_COLS}) VALUES({','.join('?' * 19)})",
            (i.id, i.reporter_id, i.title, i.description, i.category, i.service_id, i.impact, i.urgency, i.affected_users,
             i.priority.name if i.priority else None, i.status.value, i.assigned_to, i.created_at.isoformat(), i.resolution,
             _iso(i.acknowledged_at), _iso(i.resolved_at), _iso(i.closed_at),
             _iso(sla.response_due) if sla else None, _iso(sla.resolution_due) if sla else None))
    def get(self, incident_id):
        rows = self._db.query("SELECT * FROM incidents WHERE id=?", (incident_id,)); return _incident(rows[0]) if rows else None
    def list_by_reporter(self, user_id):
        return [_incident(r) for r in self._db.query("SELECT * FROM incidents WHERE reporter_id=? ORDER BY created_at DESC", (user_id,))]
    def list_by_assignee(self, technician_id):
        return [_incident(r) for r in self._db.query("SELECT * FROM incidents WHERE assigned_to=? AND status<>? ORDER BY created_at", (technician_id, Status.CLOSED.value))]
    def list_unresolved(self):
        rows = self._db.query("SELECT * FROM incidents WHERE status IN (?,?,?,?,?) ORDER BY created_at", tuple(s.value for s in _OPEN))
        return [_incident(r) for r in rows]
    def count_active_by_technician(self, technician_id):
        active = (Status.ASSIGNED.value, Status.ACKNOWLEDGED.value, Status.IN_PROGRESS.value)
        return self._db.query("SELECT COUNT(*) c FROM incidents WHERE assigned_to=? AND status IN (?,?,?)", (technician_id, *active))[0]["c"]
    def search(self, f, limit=50, offset=0):
        raise NotImplementedError("TODO(Gaurav): build WHERE from IncidentFilter (>=5 criteria), ORDER BY created_at DESC, LIMIT/OFFSET")

class SqliteAuditRepository(AuditRepository):
    def __init__(self, db: Database): self._db = db
    def append(self, a):
        self._db.execute("INSERT INTO audit_records(incident_id,actor_id,action,old_status,new_status,description,timestamp) VALUES(?,?,?,?,?,?,?)",
            (a.incident_id, a.actor_id, a.action, a.old_status, a.new_status, a.description, a.timestamp.isoformat()))
    @staticmethod
    def _rec(r): return AuditRecord(r["incident_id"], r["actor_id"], r["action"], r["old_status"], r["new_status"], r["description"], _dt(r["timestamp"]))
    def list_for_incident(self, incident_id):
        return [self._rec(r) for r in self._db.query("SELECT * FROM audit_records WHERE incident_id=? ORDER BY id", (incident_id,))]
    def list_all(self, limit=200):
        return [self._rec(r) for r in self._db.query("SELECT * FROM audit_records ORDER BY id DESC LIMIT ?", (limit,))]

class SqliteServiceRepository(ServiceRepository):
    def __init__(self, db: Database): self._db = db
    @staticmethod
    def _svc(r): return Service(r["id"], r["name"], r["criticality"])
    def get(self, service_id):
        rows = self._db.query("SELECT * FROM services WHERE id=?", (service_id,)); return self._svc(rows[0]) if rows else None
    def list_all(self): return [self._svc(r) for r in self._db.query("SELECT * FROM services ORDER BY name")]
    def add(self, s): self._db.execute("INSERT INTO services(id,name,criticality) VALUES(?,?,?)", (s.id, s.name, s.criticality))
    def update_criticality(self, service_id, criticality): self._db.execute("UPDATE services SET criticality=? WHERE id=?", (criticality, service_id))

class SqliteSlaPolicyRepository(SlaPolicyRepository):
    def __init__(self, db: Database): self._db = db
    @staticmethod
    def _pol(r): return SlaPolicy(Priority[r["priority"]], r["response_minutes"], r["resolution_minutes"], r["service_id"])
    def get_for(self, priority, service_id="*"):
        rows = self._db.query("SELECT * FROM sla_policies WHERE priority=? AND service_id IN (?, '*') ORDER BY (service_id='*') LIMIT 1", (priority.name, service_id))
        return self._pol(rows[0]) if rows else None
    def upsert(self, p):
        self._db.execute("INSERT INTO sla_policies(service_id,priority,response_minutes,resolution_minutes) VALUES(?,?,?,?) "
                         "ON CONFLICT(service_id,priority) DO UPDATE SET response_minutes=excluded.response_minutes, resolution_minutes=excluded.resolution_minutes",
                         (p.service_id, p.priority.name, p.response_minutes, p.resolution_minutes))
    def list_all(self): return [self._pol(r) for r in self._db.query("SELECT * FROM sla_policies ORDER BY service_id, priority")]

class SqliteCategoryRepository(CategoryRepository):
    def __init__(self, db: Database): self._db = db
    def list_active(self): return [r["name"] for r in self._db.query("SELECT name FROM categories WHERE active=1 ORDER BY name")]
    def exists_active(self, name):
        try: n = normalise_category(name)
        except Exception: return False
        return bool(self._db.query("SELECT 1 FROM categories WHERE name=? AND active=1", (n,)))
    def add(self, name):
        self._db.execute("INSERT INTO categories(name,active) VALUES(?,1) ON CONFLICT(name) DO UPDATE SET active=1", (normalise_category(name),))
    def set_active(self, name, active): self._db.execute("UPDATE categories SET active=? WHERE name=?", (int(active), normalise_category(name)))
    def ensure_defaults(self, names):
        for n in names: self._db.execute("INSERT OR IGNORE INTO categories(name,active) VALUES(?,1)", (normalise_category(n),))

class SqliteSlaViolationRepository(SlaViolationRepository):
    def __init__(self, db: Database): self._db = db
    def record(self, incident_id, kind, detected_at):
        cur = self._db.execute("INSERT OR IGNORE INTO sla_violations(incident_id,kind,detected_at) VALUES(?,?,?)", (incident_id, kind, detected_at.isoformat()))
        return cur.rowcount == 1
    def list_for_incident(self, incident_id):
        return [(r["kind"], _dt(r["detected_at"])) for r in self._db.query("SELECT * FROM sla_violations WHERE incident_id=? ORDER BY detected_at", (incident_id,))]
    def list_all(self):
        return [(r["incident_id"], r["kind"], _dt(r["detected_at"])) for r in self._db.query("SELECT * FROM sla_violations ORDER BY detected_at")]

class SqliteCommentRepository(CommentRepository):
    def __init__(self, db: Database): self._db = db
    def add(self, c):
        self._db.execute("INSERT INTO comments(incident_id,author_id,kind,body,internal,created_at) VALUES(?,?,?,?,?,?)",
                         (c.incident_id, c.author_id, c.kind, c.body, int(c.internal), c.created_at.isoformat()))
    def list_for_incident(self, incident_id, include_internal=True):
        sql = "SELECT * FROM comments WHERE incident_id=?" + ("" if include_internal else " AND internal=0") + " ORDER BY id"
        return [Comment(r["incident_id"], r["author_id"], r["kind"], r["body"], bool(r["internal"]), _dt(r["created_at"])) for r in self._db.query(sql, (incident_id,))]

class SqliteFeedbackRepository(FeedbackRepository):
    def __init__(self, db: Database): self._db = db
    def add(self, f): self._db.execute("INSERT INTO feedback(incident_id,reporter_id,rating,comment) VALUES(?,?,?,?)", (f.incident_id, f.reporter_id, f.rating, f.comment))
    def get(self, incident_id):
        rows = self._db.query("SELECT * FROM feedback WHERE incident_id=?", (incident_id,))
        return Feedback(rows[0]["incident_id"], rows[0]["reporter_id"], rows[0]["rating"], rows[0]["comment"] or "") if rows else None

class SqliteConfigRepository(ConfigRepository):
    def __init__(self, db: Database): self._db = db
    def get(self, key, default=None):
        rows = self._db.query("SELECT value FROM config WHERE key=?", (key,)); return rows[0]["value"] if rows else default
    def set(self, key, value):
        self._db.execute("INSERT INTO config(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
