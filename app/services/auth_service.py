"""Authentication (owner: Kevalin). Passwords: PBKDF2-SHA256 with per-user salt, stdlib only."""
import hashlib, hmac, os
from app.domain.enums import Role
from app.domain.exceptions import AuthenticationError, ValidationError
from app.domain.models import User

class AuthService:
    def __init__(self, users): self._users = users
    @staticmethod
    def hash_password(password: str) -> str:
        salt = os.urandom(16)
        return salt.hex() + "$" + hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000).hex()
    @staticmethod
    def _verify(password: str, stored: str) -> bool:
        salt_hex, digest = stored.split("$")
        test = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), 200_000).hex()
        return hmac.compare_digest(test, digest)
    def register(self, name, email, password) -> User:
        """Self-registration ALWAYS creates an EMPLOYEE; there is deliberately no role parameter."""
        if len(password or "") < 8: raise ValidationError("Password must be at least 8 characters")
        if self._users.get_by_email(email or ""): raise ValidationError("Email already registered")
        user = User(name, email, self.hash_password(password), Role.EMPLOYEE)
        self._users.add(user); return user
    def login(self, email, password) -> User:
        user = self._users.get_by_email(email or "")
        if user is None or not self._verify(password or "", user.password_hash):
            raise AuthenticationError("Invalid email or password")   # same message for both: no user enumeration
        return user
