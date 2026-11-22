"""SQLite implementations (stdlib sqlite3 - think JDBC). Owner: Kevalin; Gaurav fills in search()."""
import sqlite3, threading
from datetime import datetime, timezone
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
    def set_password_hash(self, user_id, password_hash): self._db.execute("UPDATE users SET password_hash=? WHERE id=?", (password_hash, user_id))

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
        clauses, params = [], []
        if f.incident_id:
            clauses.append("id = ?"); params.append(f.incident_id)
        if f.status:
            clauses.append("status = ?")
            params.append(f.status.value if hasattr(f.status, "value") else str(f.status))
        if f.priority:
            clauses.append("priority = ?")
            params.append(f.priority.name if hasattr(f.priority, "name") else str(f.priority))
        if f.category:
            clauses.append("category = ?")
            params.append(normalise_category(f.category) if hasattr(f.category, "strip") else str(f.category))
        if f.service_id:
            clauses.append("service_id = ?"); params.append(f.service_id)
        if f.technician_id:
            clauses.append("assigned_to = ?"); params.append(f.technician_id)
        if f.date_from:
            clauses.append("created_at >= ?")
            params.append(f.date_from.isoformat() if hasattr(f.date_from, "isoformat") else str(f.date_from))
        if f.date_to:
            clauses.append("created_at <= ?")
            params.append(f.date_to.isoformat() if hasattr(f.date_to, "isoformat") else str(f.date_to))
        if f.text:
            pattern = f"%{f.text}%"
            clauses.append("(title LIKE ? OR description LIKE ?)")
            params.extend([pattern, pattern])
        if f.sla_status:
            if f.sla_status == "VIOLATED":
                clauses.append("id IN (SELECT incident_id FROM sla_violations WHERE kind LIKE '%VIOLATION%')")
            elif f.sla_status == "AT_RISK":
                clauses.append("id IN (SELECT incident_id FROM sla_violations WHERE kind LIKE '%WARNING%')")
            elif f.sla_status == "ON_TRACK":
                clauses.append("id NOT IN (SELECT incident_id FROM sla_violations)")

        sql = "SELECT * FROM incidents"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([int(limit), int(offset)])
        return [_incident(r) for r in self._db.query(sql, tuple(params))]
        
    def count_total(self):
        return self._db.query("SELECT COUNT(*) c FROM incidents")[0]["c"]

    def count_by_status(self, statuses):
        if not statuses:
            return 0
        values = tuple(s.value if hasattr(s, "value") else str(s) for s in statuses)
        placeholders = ",".join("?" * len(values))
        return self._db.query(
            f"SELECT COUNT(*) c FROM incidents WHERE status IN ({placeholders})",
            values,
        )[0]["c"]

    def count_critical(self):
        return self._db.query(
            "SELECT COUNT(*) c FROM incidents WHERE priority=?", (Priority.P1.name,)
        )[0]["c"]

    def technician_workload(self):
        sql = (
            "SELECT u.id, u.name, u.max_workload, "
            "COUNT(CASE WHEN i.status IN ('ASSIGNED','ACKNOWLEDGED','IN_PROGRESS') THEN 1 END) as active "
            "FROM users u "
            "LEFT JOIN incidents i ON u.id = i.assigned_to "
            "WHERE u.role = 'TECHNICIAN' AND u.active = 1 "
            "GROUP BY u.id, u.name, u.max_workload "
            "ORDER BY active DESC, u.name ASC"
        )
        return [(r["name"], r["active"], r["id"], r["max_workload"]) for r in self._db.query(sql)]

    def counts_by_service(self):
        sql = (
            "SELECT s.id, s.name, COUNT(i.id) as incident_count "
            "FROM services s "
            "LEFT JOIN incidents i ON s.id = i.service_id "
            "GROUP BY s.id, s.name "
            "ORDER BY incident_count DESC, s.name ASC"
        )
        return [(r["name"], r["incident_count"], r["id"]) for r in self._db.query(sql)]

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
    def list_actions(self) -> list[str]:
        rows = self._db.query("SELECT DISTINCT action FROM audit_records WHERE action IS NOT NULL ORDER BY action")
        return [r["action"] for r in rows if r["action"]]
    def search(self, f=None, limit=200, offset=0):
        clauses, params = [], []
        if f:
            if f.incident_id:
                clauses.append("incident_id LIKE ?")
                params.append(f"%{f.incident_id.strip()}%")
            if f.actor_id:
                clauses.append("actor_id = ?")
                params.append(f.actor_id.strip())
            if f.action:
                clauses.append("action = ?")
                params.append(f.action.strip())
            if f.text:
                pat = f"%{f.text.strip()}%"
                clauses.append("(incident_id LIKE ? OR actor_id LIKE ? OR action LIKE ? OR description LIKE ? OR old_status LIKE ? OR new_status LIKE ?)")
                params.extend([pat, pat, pat, pat, pat, pat])
            if f.date_from:
                clauses.append("timestamp >= ?")
                params.append(f.date_from.isoformat() if hasattr(f.date_from, "isoformat") else str(f.date_from))
            if f.date_to:
                clauses.append("timestamp <= ?")
                params.append(f.date_to.isoformat() if hasattr(f.date_to, "isoformat") else str(f.date_to))

        sort_by = (f.sort_by if f and f.sort_by else "timestamp").lower().strip()
        sort_dir = (f.sort_dir if f and f.sort_dir else "desc").upper().strip()
        if sort_dir not in ("ASC", "DESC"):
            sort_dir = "DESC"

        col_map = {
            "timestamp": "timestamp",
            "date": "timestamp",
            "time": "timestamp",
            "id": "id",
            "action": "action",
            "actor": "actor_id",
            "actor_id": "actor_id",
            "incident": "incident_id",
            "incident_id": "incident_id",
            "description": "description",
        }
        order_col = col_map.get(sort_by, "id")

        sql = "SELECT * FROM audit_records"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)

        if order_col in ("incident_id", "actor_id"):
            sql += f" ORDER BY ({order_col} IS NULL OR {order_col} = ''), {order_col} {sort_dir}, id DESC"
        elif order_col in ("timestamp", "date", "time"):
            sql += f" ORDER BY timestamp {sort_dir}, id {sort_dir}"
        elif order_col == "id":
            sql += f" ORDER BY id {sort_dir}"
        else:
            sql += f" ORDER BY {order_col} {sort_dir}, id DESC"

        sql += " LIMIT ? OFFSET ?"
        params.extend([int(limit), int(offset)])
        return [self._rec(r) for r in self._db.query(sql, tuple(params))]

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
        
    def count_violated_incidents(self):
        return self._db.query(
            "SELECT COUNT(DISTINCT incident_id) c FROM sla_violations WHERE kind LIKE '%VIOLATION'"
        )[0]["c"]
        
        

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

class SqliteNotificationRepository(NotificationRepository):
    def __init__(self, db: Database): self._db = db
    def add(self, recipient_id, channel, subject, body, status="SENT", created_at=None):
        dt = created_at or datetime.now(timezone.utc)
        cur = self._db.execute(
            "INSERT INTO notifications(recipient_id,channel,subject,body,status,created_at,is_read) VALUES(?,?,?,?,?,?,0)",
            (recipient_id, channel, subject, body, status, dt.isoformat())
        )
        return cur.lastrowid
    def list_for_recipient(self, recipient_id, unread_only=False, channel=None):
        sql = "SELECT * FROM notifications WHERE recipient_id=?"
        params = [recipient_id]
        if unread_only:
            sql += " AND is_read=0"
        if channel is not None:
            sql += " AND channel=?"
            params.append(channel)
        sql += " ORDER BY id DESC"
        return [dict(r) for r in self._db.query(sql, tuple(params))]
    def count_unread(self, recipient_id, channel="IN_APP"):
        rows = self._db.query(
            "SELECT COUNT(*) AS c FROM notifications WHERE recipient_id=? AND is_read=0 AND channel=?",
            (recipient_id, channel)
        )
        return rows[0]["c"]
    def mark_read(self, notification_id, recipient_id):
        self._db.execute(
            "UPDATE notifications SET is_read=1 WHERE id=? AND recipient_id=?",
            (notification_id, recipient_id)
        )
    def mark_all_read(self, recipient_id):
        self._db.execute("UPDATE notifications SET is_read=1 WHERE recipient_id=?", (recipient_id,))
