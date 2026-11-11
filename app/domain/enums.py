from enum import Enum

class Role(str, Enum):
    EMPLOYEE = "EMPLOYEE"; TECHNICIAN = "TECHNICIAN"; ADMIN = "ADMIN"

class Status(str, Enum):
    NEW = "NEW"; CLASSIFIED = "CLASSIFIED"; ASSIGNED = "ASSIGNED"; ACKNOWLEDGED = "ACKNOWLEDGED"
    IN_PROGRESS = "IN_PROGRESS"; RESOLVED = "RESOLVED"; VERIFIED = "VERIFIED"; CLOSED = "CLOSED"

class Priority(Enum):
    P1 = 1; P2 = 2; P3 = 3; P4 = 4   # P1 = Critical ... P4 = Low

class Category(str, Enum):  # add members freely; nothing else switches on the full list
    HARDWARE = "HARDWARE"; SOFTWARE = "SOFTWARE"; NETWORK = "NETWORK"; DATABASE = "DATABASE"
    CLOUD = "CLOUD"; SECURITY = "SECURITY"; AUTHENTICATION = "AUTHENTICATION"
    APPLICATION = "APPLICATION"; STORAGE = "STORAGE"
