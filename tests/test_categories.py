import pytest
from app.domain.exceptions import AuthorizationError, ValidationError

def _report(c, category):
    return c.incident_service.create_incident(c.users.get_by_email("e1@itsm.local"), "Title", "Desc", category, "SVC-PAY", 3, 3)

def test_defaults_are_seeded(c): assert "DATABASE" in c.categories.list_active()

def test_unknown_category_rejected(c):
    with pytest.raises(ValidationError): _report(c, "ANALYTICS")

def test_admin_adds_category_and_it_is_usable_and_normalised(c):
    c.admin.add_category(c.users.get_by_email("admin@itsm.local"), "analytics")
    assert _report(c, "analytics").category == "ANALYTICS"

def test_employee_cannot_add_category(c):
    with pytest.raises(AuthorizationError): c.admin.add_category(c.users.get_by_email("e1@itsm.local"), "SNEAKY")

def test_disabled_category_rejected_for_new_incidents(c):
    c.admin.disable_category(c.users.get_by_email("admin@itsm.local"), "STORAGE")
    with pytest.raises(ValidationError): _report(c, "STORAGE")

def test_invalid_category_name_rejected(c):
    with pytest.raises(ValidationError): c.admin.add_category(c.users.get_by_email("admin@itsm.local"), "x; DROP TABLE")
