import pytest
from app.domain.enums import Category, Status
from app.domain.exceptions import AuthorizationError

def _create(c, email="e1@itsm.local"):
    return c.incident_service.create_incident(c.users.get_by_email(email), "Payment down", "Cannot pay", Category.APPLICATION, "SVC-PAY", 5, 5, 100)

def test_create_persists_and_is_audited(c):
    inc = _create(c)
    assert c.incidents.get(inc.id).status == Status.CLASSIFIED
    assert [a.action for a in c.audit.list_for_incident(inc.id)] == ["INCIDENT_CREATED", "INCIDENT_CLASSIFIED"]

def test_employee_cannot_view_another_employees_incident(c):
    inc = _create(c)
    with pytest.raises(AuthorizationError): c.incident_service.get_incident(c.users.get_by_email("e2@itsm.local"), inc.id)

def test_only_assigned_technician_can_acknowledge(c):   # TODO(Kevalin)
    inc = _create(c); c.incident_service.assign_incident(c.users.get_by_email("admin@itsm.local"), inc.id, "U-T1")
    with pytest.raises(AuthorizationError): c.incident_service.acknowledge(c.users.get_by_email("t2@itsm.local"), inc.id)
