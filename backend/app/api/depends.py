from enum import StrEnum
from uuid import UUID

from authx import TokenPayload
from fastapi import Depends, HTTPException, status

from ..config.security import security
from ..crud import user as crud_user
from ..database.db import SessionDep
from ..database.models import User, UserStatus


async def get_current_user(
    session: SessionDep, payload: TokenPayload = Depends(security.access_token_required)
) -> User:
    user_id = UUID(payload.sub)
    user = await crud_user.get_user_by_id(session=session, user_id=user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    if user.status is not UserStatus.active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is inactive")
    return user


class Role(StrEnum):
    admin = "admin"
    manager = "manager"
    user = "user"


class RoleChecker:
    def __init__(self, allowed_roles: list[Role]) -> None:
        self.allowed_roles = allowed_roles

    async def __call__(self, user: User = Depends(get_current_user)):
        if user.is_superuser:
            return user

        if user.role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden"
            )
        return user
