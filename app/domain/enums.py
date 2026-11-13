from enum import Enum

class Role(str, Enum):
    EMPLOYEE = "EMPLOYEE"; TECHNICIAN = "TECHNICIAN"; ADMIN = "ADMIN"
    TEAM_LEAD = "TEAM_LEAD"; IT_MANAGER = "IT_MANAGER"   # escalation chain: technician -> team lead -> admin -> IT manager

class Status(str, Enum):
    NEW = "NEW"; CLASSIFIED = "CLASSIFIED"; ASSIGNED = "ASSIGNED"; ACKNOWLEDGED = "ACKNOWLEDGED"
    IN_PROGRESS = "IN_PROGRESS"; RESOLVED = "RESOLVED"; VERIFIED = "VERIFIED"; CLOSED = "CLOSED"

class Priority(Enum):
    P1 = 1; P2 = 2; P3 = 3; P4 = 4   # P1 = Critical ... P4 = Low

class CommentKind(str, Enum):
    NOTE = "NOTE"; REQUEST = "REQUEST"; REPLY = "REPLY"   # technician note | technician asks reporter | reporter answers

class Category:
    """Names seeded into the `categories` table on first run. NOT an Enum any more: the live list is the
    table (admins can add more). Plain strings, so Category.DATABASE == "DATABASE" and old tests still work."""
    HARDWARE = "HARDWARE"; SOFTWARE = "SOFTWARE"; NETWORK = "NETWORK"; DATABASE = "DATABASE"
    CLOUD = "CLOUD"; SECURITY = "SECURITY"; AUTHENTICATION = "AUTHENTICATION"
    APPLICATION = "APPLICATION"; STORAGE = "STORAGE"
    DEFAULTS = (HARDWARE, SOFTWARE, NETWORK, DATABASE, CLOUD, SECURITY, AUTHENTICATION, APPLICATION, STORAGE)
