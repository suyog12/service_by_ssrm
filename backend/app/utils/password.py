import hashlib
import hmac
from passlib.context import CryptContext

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
    bcrypt__rounds=12
)


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")[:72]
    return pwd_context.hash(password_bytes.decode("utf-8", errors="ignore"))


def verify_password(plain_password: str, hashed_password: str) -> bool:
    password_bytes = plain_password.encode("utf-8")[:72]
    return pwd_context.verify(password_bytes.decode("utf-8", errors="ignore"), hashed_password)


def hash_token(token: str) -> str:
    """SHA-256 hash for machine-generated tokens (refresh tokens, reset tokens)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def verify_token(plain_token: str, hashed_token: str) -> bool:
    """Constant-time comparison of SHA-256 token hashes."""
    return hmac.compare_digest(
        hashlib.sha256(plain_token.encode("utf-8")).hexdigest(),
        hashed_token
    )