import pytest
from app.domain.exceptions import AuthenticationError

def test_password_is_hashed(c):
    u = c.auth.register("New User", "new@x.io", "longenough1"); assert "longenough1" not in u.password_hash

def test_wrong_password_rejected(c):
    with pytest.raises(AuthenticationError): c.auth.login("e1@itsm.local", "wrong")

def test_registration_always_creates_employee(c):
    assert c.auth.register("Sneaky", "s@x.io", "longenough1").role.value == "EMPLOYEE"
