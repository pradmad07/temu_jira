"""Dashboards & Management Reports (owner: Gaurav). All data comes from repository queries; no SQL here."""
from app.domain.enums import Status


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


_OPEN_STATUSES = (Status.NEW, Status.CLASSIFIED, Status.ASSIGNED, Status.ACKNOWLEDGED, Status.IN_PROGRESS)
_RESOLVED_STATUSES = (Status.RESOLVED, Status.VERIFIED, Status.CLOSED)


class ReportService:
    def __init__(self, incidents, violations=None):
        self._incidents = incidents
        self._violations = violations

    def overview(self) -> dict:
        """total, open, critical, resolved, sla_violations."""
        return {
            "total": self._incidents.count_total(),
            "open": self._incidents.count_by_status(_OPEN_STATUSES),
            "critical": self._incidents.count_critical(),
            "resolved": self._incidents.count_by_status(_RESOLVED_STATUSES),
            "sla_violations": self._violations.count_violated_incidents() if self._violations else 0,
        }

    def technician_workload(self) -> list[WorkloadRow]:
        """(technician_name, active_count) per active technician, sorted by active desc then name."""
        return [
            WorkloadRow(name, active, tid, maxw)
            for name, active, tid, maxw in self._incidents.technician_workload()
        ]

    def service_counts(self) -> list[ServiceCountRow]:
        """(service_name, incident_count) per service, sorted by count desc then name."""
        return [
            ServiceCountRow(name, count, sid)
            for name, count, sid in self._incidents.counts_by_service()
        ]
