from datetime import datetime, timedelta, timezone
from typing import Optional
from jose import JWTError, jwt
import secrets
from app.core.config import settings


def create_access_token(data: dict) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload.update({"exp": expire, "type": "access"})
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )


def create_refresh_token(data: dict) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(
        days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS
    )
    # jti ensures every refresh token is unique even if generated
    # for the same user within the same second
    payload.update({
        "exp": expire,
        "type": "refresh",
        "jti": secrets.token_hex(16)
    })
    return jwt.encode(
        payload,
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM
    )


def decode_token(token: str) -> Optional[dict]:
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
    except JWTError:
        return None