from app.domain.permissions import Perm

def test_employee_can_create_but_not_assign(c):
    e = c.users.get_by_email("e1@itsm.local")
    assert e.can(Perm.INCIDENT_CREATE) and not e.can(Perm.INCIDENT_ASSIGN)

def test_admin_can_assign_technician_cannot(c):
    assert c.users.get_by_email("admin@itsm.local").can(Perm.INCIDENT_ASSIGN)
    assert not c.users.get_by_email("t1@itsm.local").can(Perm.INCIDENT_ASSIGN)

def test_admin_can_view_any_incident_technician_only_assigned(c):
    from app.domain.enums import Category
    from app.domain.exceptions import AuthorizationError
    import pytest
    inc = c.incident_service.create_incident(c.users.get_by_email("e1@itsm.local"), "Db slow", "queries slow", Category.DATABASE, "SVC-DB", 3, 3)
    assert c.incident_service.get_incident(c.users.get_by_email("admin@itsm.local"), inc.id).id == inc.id
    with pytest.raises(AuthorizationError): c.incident_service.get_incident(c.users.get_by_email("t1@itsm.local"), inc.id)
