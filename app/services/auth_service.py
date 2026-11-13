"""Authentication (owner: Kevalin).
Passwords: PBKDF2-HMAC-SHA256 with a per-user random salt. The work factor (iteration count) is stored INSIDE each hash,
`pbkdf2_sha256$<iterations>$<salt>$<hash>`, so it can be raised later without locking anyone out: old hashes verify with
their own number and are upgraded to the current one the next time that user logs in."""
import hashlib, hmac, os, secrets
from app.domain.enums import Role
from app.domain.exceptions import AuthenticationError, ValidationError
from app.domain.factories import UserFactory
from app.domain.models import User

ALGO = "pbkdf2_sha256"
ITERATIONS = 600_000        # raise this over time as hardware gets faster
LEGACY_ITERATIONS = 200_000 # hashes written by the first version had no stored count ("salt$hash")

def _derive(password: str, salt: bytes, iterations: int) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations).hex()

class AuthService:
    def __init__(self, users, sso_domains=None):
        self._users = users
        self._sso_domains = [d.lower() for d in sso_domains] if sso_domains else None   # None = any verified email

    @staticmethod
    def hash_password(password: str, iterations: int = ITERATIONS) -> str:
        salt = os.urandom(16)
        return f"{ALGO}${iterations}${salt.hex()}${_derive(password, salt, iterations)}"

    @staticmethod
    def _parse(stored: str):
        """-> (iterations, salt_bytes, digest_hex) or None when the stored value is unusable."""
        try:
            parts = stored.split("$")
            if len(parts) == 2: return LEGACY_ITERATIONS, bytes.fromhex(parts[0]), parts[1]
            if len(parts) == 4 and parts[0] == ALGO: return int(parts[1]), bytes.fromhex(parts[2]), parts[3]
        except (ValueError, AttributeError): pass
        return None

    @classmethod
    def _verify(cls, password: str, stored: str) -> bool:
        parsed = cls._parse(stored)
        if parsed is None: return False                  # unusable hash: refuse, never crash
        iterations, salt, digest = parsed
        return hmac.compare_digest(_derive(password, salt, iterations), digest)

    @classmethod
    def needs_rehash(cls, stored: str) -> bool:
        parsed = cls._parse(stored)
        return parsed is not None and (len(stored.split("$")) == 2 or parsed[0] < ITERATIONS)

    def register(self, name, email, password) -> User:
        """Self-registration ALWAYS creates an EMPLOYEE; there is deliberately no role parameter."""
        if len(password or "") < 8: raise ValidationError("Password must be at least 8 characters")
        if self._users.get_by_email(email or ""): raise ValidationError("Email already registered")
        user = UserFactory.create(Role.EMPLOYEE, name, email, self.hash_password(password))
        self._users.add(user); return user

    def login(self, email, password) -> User:
        user = self._users.get_by_email(email or "")
        # Always do one hash computation, even for an unknown email, so response time does not reveal which emails exist.
        ok = self._verify(password or "", user.password_hash if user else _DUMMY_HASH)
        if user is None or not user.active or not ok:
            raise AuthenticationError("Invalid email or password")   # same message for every failure: no user enumeration
        if self.needs_rehash(user.password_hash):                    # transparent upgrade: we only have the plaintext right now
            self._users.set_password_hash(user.id, self.hash_password(password))
        return user

    def login_with_identity(self, email, name, email_verified) -> User:
        """Single sign-on (Google). Rules: the provider must vouch for the email; optionally only approved domains;
        an existing account logs in AS ITSELF (roles are never changed by SSO); an unknown email becomes an EMPLOYEE;
        disabled accounts stay locked out. SSO-only accounts get a random password nobody knows."""
        email = (email or "").strip().lower()
        if not email or not email_verified: raise AuthenticationError("Your email address is not verified by the provider")
        if self._sso_domains and email.rsplit("@", 1)[-1] not in self._sso_domains:
            raise AuthenticationError("Sign-in is limited to approved email domains")
        user = self._users.get_by_email(email)
        if user is None:
            user = UserFactory.create(Role.EMPLOYEE, (name or "").strip() or email.split("@")[0], email, self.hash_password(secrets.token_hex(32)))
            self._users.add(user)
        elif not user.active: raise AuthenticationError("This account is disabled")
        return user

_DUMMY_HASH = AuthService.hash_password(secrets.token_hex(8))
