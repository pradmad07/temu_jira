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
