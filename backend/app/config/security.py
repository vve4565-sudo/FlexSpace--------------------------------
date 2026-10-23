from pwdlib import PasswordHash
from authx import AuthX, AuthXConfig
from .config import settings

ph = PasswordHash.recommended()

dummyhash = "dummyhashpassword"


def hash_password(password: str) -> str:
    return ph.hash(password)


def verify_password(
    plain_password: str, hashed_password: str
) -> tuple[bool, str | None]:
    return ph.verify_and_update(plain_password, hashed_password)


config = AuthXConfig(
    JWT_ACCESS_TOKEN_EXPIRES=settings.ACCESS_TOKEN_EXPIRE_MINUTES,
    JWT_REFRESH_TOKEN_EXPIRES=settings.REFRESH_TOKEN_EXPIRE_DAYS,
    JWT_SECRET_KEY=settings.JWT_SECRET_KEY,
    JWT_ALGORITHM=settings.JWT_ALGORITHM,  # type: ignore
    JWT_TOKEN_LOCATION=settings.JWT_TOKEN_LOCATION,  # type: ignore
    JWT_REFRESH_COOKIE_NAME=settings.JWT_REFRESH_COOKIE_NAME,
    JWT_ACCESS_COOKIE_NAME=settings.JWT_ACCESS_COOKIE_NAME,
    JWT_COOKIE_CSRF_PROTECT=settings.JWT_COOKIE_CSRF_PROTECT,
)

security = AuthX(config)


