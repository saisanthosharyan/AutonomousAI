from datetime import datetime, timedelta, UTC

from app.core.config import settings
import jwt
from passlib.context import CryptContext

from app.core.config import settings


pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(
    password: str,
    password_hash: str,
) -> bool:
    return pwd_context.verify(
        password,
        password_hash,
    )


def create_access_token(
    user_id: int,
    username: str,
) -> str:
    expires_at = datetime.now(UTC) + timedelta(
        hours=settings.JWT_EXPIRATION_HOURS,
    )

    payload = {
        "sub": str(user_id),
        "username": username,
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        settings.SECRET_KEY,
        algorithm="HS256",
    )


def decode_access_token(token: str) -> dict:
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=["HS256"],
    )