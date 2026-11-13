import hashlib, os
import pytest
from app.container import build_container
from app.domain.enums import Role
from app.domain.exceptions import AuthenticationError
from app.domain.models import User
from app.seed import seed
from app.services.auth_service import AuthService, ITERATIONS
from tests.helpers import FakeClock, user

def _legacy_hash(pw):    # the first version's format: "salt$hash", 200,000 iterations, count not stored
    salt = os.urandom(16); return salt.hex() + "$" + hashlib.pbkdf2_hmac("sha256", pw.encode(), salt, 200_000).hex()

def test_new_hashes_carry_their_own_work_factor():
    assert AuthService.hash_password("pw12345678").startswith(f"pbkdf2_sha256${ITERATIONS}$")

def test_each_hash_is_verified_with_its_own_iteration_count():
    weak = AuthService.hash_password("pw12345678", iterations=1000)
    assert AuthService._verify("pw12345678", weak) and not AuthService._verify("wrong-pw", weak)

def test_old_format_hash_still_logs_in_and_is_upgraded(c):
    c.users.add(User("Old Timer", "old@x.io", _legacy_hash("oldpassword1"), Role.EMPLOYEE))
    c.auth.login("old@x.io", "oldpassword1")
    upgraded = c.users.get_by_email("old@x.io").password_hash
    assert upgraded.startswith(f"pbkdf2_sha256${ITERATIONS}$")
    c.auth.login("old@x.io", "oldpassword1")                         # still works after the upgrade

def test_unusable_stored_hash_is_refused_not_a_crash(c):
    c.users.add(User("Broken", "broken@x.io", "!", Role.EMPLOYEE))
    with pytest.raises(AuthenticationError): c.auth.login("broken@x.io", "anything")

def test_unknown_email_and_wrong_password_look_identical(c):
    msgs = []
    for email, pw in [("nobody@x.io", "whatever1"), ("e1@itsm.local", "wrongpass1")]:
        with pytest.raises(AuthenticationError) as e: c.auth.login(email, pw)
        msgs.append(str(e.value))
    assert msgs[0] == msgs[1]

# ---- single sign-on rules (the Google round trip itself needs the real provider; the decisions are testable)
def test_sso_creates_an_employee_for_a_new_verified_email(c):
    u = c.auth.login_with_identity("New.Person@Example.com", "New Person", True)
    assert u.role == Role.EMPLOYEE and u.email == "new.person@example.com" and c.users.get(u.id) is not None

def test_sso_rejects_unverified_email(c):
    with pytest.raises(AuthenticationError): c.auth.login_with_identity("x@example.com", "X", False)

def test_sso_logs_existing_staff_in_as_themselves_never_as_something_else(c):
    assert c.auth.login_with_identity("t1@itsm.local", "Whoever", True).role == Role.TECHNICIAN

def test_sso_cannot_reactivate_a_disabled_account(c):
    c.admin.set_user_active(user(c, "admin@itsm.local"), "U-E2", False)
    with pytest.raises(AuthenticationError): c.auth.login_with_identity("e2@itsm.local", "Ravi", True)

def test_sso_domain_allow_list():
    c = build_container(":memory:", clock=FakeClock(), auto_assign=False); seed(c)
    restricted = AuthService(c.users, sso_domains=["itsm.local"])
    assert restricted.login_with_identity("fresh@itsm.local", "Fresh", True).email == "fresh@itsm.local"
    with pytest.raises(AuthenticationError): restricted.login_with_identity("outsider@gmail.com", "Out", True)

def test_sso_only_account_cannot_be_entered_with_a_guessed_password(c):
    c.auth.login_with_identity("sso.only@example.com", "Sso Only", True)
    with pytest.raises(AuthenticationError): c.auth.login("sso.only@example.com", "password123")
