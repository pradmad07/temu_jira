"""Dashboards & Management Reports (owner: Gaurav)."""
from typing import Optional, NamedTuple
from app.domain.enums import Status, Priority, Role
from app.domain.filters import IncidentFilter

class WorkloadRow(tuple):
    """Named tuple-compatible row for technician workload: (technician_name, active_count)."""
    def __new__(cls, name: str, active_count: int, technician_id: str = "", max_workload: int = 5):
        inst = super().__new__(cls, (name, active_count))
        inst.name = name
        inst.active_count = active_count
        inst.technician_id = technician_id
        inst.max_workload = max_workload
        return inst

class ServiceCountRow(tuple):
    """Named tuple-compatible row for service counts: (service_name, incident_count)."""
    def __new__(cls, service_name: str, count: int, service_id: str = ""):
        inst = super().__new__(cls, (service_name, count))
        inst.service_name = service_name
        inst.count = count
        inst.service_id = service_id
        return inst

class ReportService:
    def __init__(self, incidents, violations=None, users=None, services=None):
        self._incidents = incidents
        self._violations = violations
        self._users = users
        self._services = services

    def overview(self) -> dict:
        """total, open, critical, resolved, sla_violations"""
        if hasattr(self._incidents, "_db"):
            db = self._incidents._db
            total = db.query("SELECT COUNT(*) c FROM incidents")[0]["c"]
            open_cnt = db.query(
                "SELECT COUNT(*) c FROM incidents WHERE status IN ('NEW','CLASSIFIED','ASSIGNED','ACKNOWLEDGED','IN_PROGRESS')"
            )[0]["c"]
            crit_cnt = db.query("SELECT COUNT(*) c FROM incidents WHERE priority='P1'")[0]["c"]
            res_cnt = db.query("SELECT COUNT(*) c FROM incidents WHERE status IN ('RESOLVED','VERIFIED','CLOSED')")[0]["c"]
            sla_cnt = db.query("SELECT COUNT(DISTINCT incident_id) c FROM sla_violations")[0]["c"]
            return {
                "total": total,
                "open": open_cnt,
                "critical": crit_cnt,
                "resolved": res_cnt,
                "sla_violations": sla_cnt,
            }

        # In-memory fallback
        all_incidents = self._incidents.search(IncidentFilter()) if hasattr(self._incidents, "search") else []
        open_statuses = (Status.NEW, Status.CLASSIFIED, Status.ASSIGNED, Status.ACKNOWLEDGED, Status.IN_PROGRESS)
        resolved_statuses = (Status.RESOLVED, Status.VERIFIED, Status.CLOSED)

        total = len(all_incidents)
        open_cnt = sum(1 for i in all_incidents if i.status in open_statuses)
        crit_cnt = sum(1 for i in all_incidents if i.priority == Priority.P1)
        res_cnt = sum(1 for i in all_incidents if i.status in resolved_statuses)

        sla_cnt = 0
        if self._violations and hasattr(self._violations, "list_all"):
            sla_cnt = len(set(r[0] for r in self._violations.list_all()))

        return {
            "total": total,
            "open": open_cnt,
            "critical": crit_cnt,
            "resolved": res_cnt,
            "sla_violations": sla_cnt,
        }

    def technician_workload(self) -> list[tuple]:
        """Returns list of (technician_name, active_count) sorted by active count desc."""
        if hasattr(self._incidents, "_db"):
            db = self._incidents._db
            sql = (
                "SELECT u.id, u.name, u.max_workload, "
                "COUNT(CASE WHEN i.status IN ('ASSIGNED','ACKNOWLEDGED','IN_PROGRESS') THEN 1 END) as active "
                "FROM users u "
                "LEFT JOIN incidents i ON u.id = i.assigned_to "
                "WHERE u.role = 'TECHNICIAN' AND u.active = 1 "
                "GROUP BY u.id, u.name, u.max_workload "
                "ORDER BY active DESC, u.name ASC"
            )
            rows = db.query(sql)
            return [WorkloadRow(r["name"], r["active"], r["id"], r["max_workload"]) for r in rows]

        if self._users and hasattr(self._users, "list_technicians"):
            technicians = self._users.list_technicians()
            results = []
            for t in technicians:
                count = self._incidents.count_active_by_technician(t.id) if hasattr(self._incidents, "count_active_by_technician") else 0
                results.append(WorkloadRow(t.name, count, t.id, t.max_workload))
            results.sort(key=lambda r: (-r.active_count, r.name))
            return results

        return []

    def service_counts(self) -> list[tuple]:
        """Returns list of (service_name, incident_count) sorted by count desc."""
        if hasattr(self._incidents, "_db"):
            db = self._incidents._db
            sql = (
                "SELECT s.id, s.name, COUNT(i.id) as incident_count "
                "FROM services s "
                "LEFT JOIN incidents i ON s.id = i.service_id "
                "GROUP BY s.id, s.name "
                "ORDER BY incident_count DESC, s.name ASC"
            )
            rows = db.query(sql)
            return [ServiceCountRow(r["name"], r["incident_count"], r["id"]) for r in rows]

        if self._services and hasattr(self._services, "list_all"):
            services = self._services.list_all()
            all_incidents = self._incidents.search(IncidentFilter()) if hasattr(self._incidents, "search") else []
            counts = {s.id: 0 for s in services}
            for inc in all_incidents:
                if inc.service_id in counts:
                    counts[inc.service_id] += 1
            results = [ServiceCountRow(s.name, counts[s.id], s.id) for s in services]
            results.sort(key=lambda r: (-r.count, r.service_name))
            return results

        return []
