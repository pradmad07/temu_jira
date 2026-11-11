-- Shared contract. Tell the others in the group chat before changing any table.
CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY, name TEXT NOT NULL, email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL, role TEXT NOT NULL, skills TEXT DEFAULT '', experience_years INTEGER DEFAULT 0,
  available INTEGER DEFAULT 1, max_workload INTEGER DEFAULT 5);
CREATE TABLE IF NOT EXISTS services(id TEXT PRIMARY KEY, name TEXT UNIQUE NOT NULL, criticality INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS sla_policies(priority TEXT PRIMARY KEY, response_minutes INTEGER NOT NULL, resolution_minutes INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS incidents(id TEXT PRIMARY KEY, reporter_id TEXT NOT NULL REFERENCES users(id),
  title TEXT NOT NULL, description TEXT NOT NULL, category TEXT NOT NULL, service_id TEXT NOT NULL REFERENCES services(id),
  impact INTEGER, urgency INTEGER, affected_users INTEGER, priority TEXT, status TEXT NOT NULL,
  assigned_to TEXT REFERENCES users(id), created_at TEXT NOT NULL, resolution TEXT);
CREATE TABLE IF NOT EXISTS audit_records(id INTEGER PRIMARY KEY AUTOINCREMENT, incident_id TEXT, actor_id TEXT,
  action TEXT, old_status TEXT, new_status TEXT, description TEXT, timestamp TEXT);
CREATE TABLE IF NOT EXISTS comments(id INTEGER PRIMARY KEY AUTOINCREMENT, incident_id TEXT, author_id TEXT,
  kind TEXT, body TEXT, internal INTEGER DEFAULT 0, created_at TEXT);  -- kind: NOTE | REQUEST | REPLY
CREATE TABLE IF NOT EXISTS notifications(id INTEGER PRIMARY KEY AUTOINCREMENT, recipient_id TEXT, channel TEXT,
  subject TEXT, body TEXT, status TEXT, created_at TEXT, is_read INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS sla_violations(incident_id TEXT, kind TEXT, detected_at TEXT, PRIMARY KEY(incident_id, kind));
CREATE TABLE IF NOT EXISTS feedback(incident_id TEXT PRIMARY KEY, reporter_id TEXT, rating INTEGER, comment TEXT);
CREATE TABLE IF NOT EXISTS incident_links(incident_id TEXT, related_id TEXT, score REAL, confirmed INTEGER DEFAULT 0,
  PRIMARY KEY(incident_id, related_id));
CREATE TABLE IF NOT EXISTS config(key TEXT PRIMARY KEY, value TEXT);  -- e.g. assignment_strategy
