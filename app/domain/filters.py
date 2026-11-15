"""Query object for incident search: typed and explainable, instead of **kwargs (owner: Gaurav implements the SQL)."""
from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from .enums import Status, Priority

@dataclass
class IncidentFilter:
    incident_id: Optional[str] = None
    status: Optional[Status] = None
    priority: Optional[Priority] = None
    category: Optional[str] = None
    service_id: Optional[str] = None
    technician_id: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    text: Optional[str] = None          # substring match on title/description
    sla_status: Optional[str] = None    # "ON_TRACK" | "AT_RISK" | "VIOLATED"

@dataclass
class AuditFilter:
    text: Optional[str] = None          # substring match on incident_id, actor_id, action, description, status
    action: Optional[str] = None        # exact action or type
    incident_id: Optional[str] = None   # target incident id
    actor_id: Optional[str] = None      # actor user id
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    sort_by: str = "timestamp"          # "timestamp", "action", "incident_id", "actor_id"
    sort_dir: str = "desc"              # "asc" | "desc"

