"""Dashboards (owner: Gaurav)."""
class ReportService:
    def __init__(self, incidents): self._incidents = incidents
    def overview(self) -> dict: """total, open, critical, resolved, sla_violations""" ; raise NotImplementedError("TODO(Gaurav)")
    def technician_workload(self) -> list[tuple]: raise NotImplementedError("TODO(Gaurav)")
    def service_counts(self) -> list[tuple]: raise NotImplementedError("TODO(Gaurav)")
