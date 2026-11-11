"""Observer that writes every event to the append-only audit trail (owner: Kevalin)."""
from app.domain.models import AuditRecord

class AuditObserver:
    def __init__(self, audit_repo): self._repo = audit_repo
    def on_event(self, e):
        self._repo.append(AuditRecord(e.incident_id, e.actor_id, e.type, e.old_status, e.new_status, e.description, e.timestamp))
