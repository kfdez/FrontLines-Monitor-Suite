"""Admin authentication helpers for the web UI."""
import base64
import hashlib
import hmac
import os
import secrets


ALGORITHM = "pbkdf2_sha256"
ITERATIONS = 260000


def hash_password(password: str, iterations: int = ITERATIONS) -> str:
    """Create a Django-style PBKDF2-SHA256 password hash."""
    salt = secrets.token_urlsafe(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    encoded = base64.b64encode(digest).decode("ascii")
    return f"{ALGORITHM}${iterations}${salt}${encoded}"


def verify_password(password: str, encoded_hash: str) -> bool:
    """Verify a password against a hash produced by hash_password."""
    try:
        algorithm, iterations, salt, encoded = encoded_hash.split("$", 3)
        if algorithm != ALGORITHM:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt.encode("utf-8"),
            int(iterations),
        )
        expected = base64.b64decode(encoded.encode("ascii"))
        return hmac.compare_digest(digest, expected)
    except Exception:
        return False


def authenticate(username: str, password: str) -> tuple[bool, str]:
    """Authenticate against env-backed admin credentials."""
    expected_user = os.environ.get("FRONTLINES_ADMIN_USERNAME", "admin")
    password_hash = os.environ.get("FRONTLINES_ADMIN_PASSWORD_HASH", "")
    if not password_hash:
        return False, "FRONTLINES_ADMIN_PASSWORD_HASH is not configured."
    if not hmac.compare_digest(username, expected_user):
        return False, "Invalid credentials."
    if not verify_password(password, password_hash):
        return False, "Invalid credentials."
    return True, ""
