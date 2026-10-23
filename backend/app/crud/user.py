import logging
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..config.security import hash_password
from ..database.models import User, UserRole, UserStatus
from ..shemas.user import SUserBase, SUserCreate

logger = logging.getLogger(__name__)


async def create_user(session: AsyncSession, user: SUserCreate) -> User:
    new_user = User(
        password_hash=hash_password(user.password),
        role=UserRole.user,
        status=UserStatus.active,
        is_superuser=False,
        **user.model_dump(exclude={"password"}),
    )
    session.add(new_user)
    await session.flush()
    logger.info("User created user_id=%s", new_user.id)
    return new_user


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    return await session.scalar(select(User).where(User.email == email))


async def get_user_by_id(session: AsyncSession, user_id: UUID) -> User | None:
    return await session.scalar(select(User).where(User.id == user_id))


async def get_user_with_bookings(session: AsyncSession, user_id: UUID) -> User | None:
    result = await session.execute(
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.bookings))
    )
    return result.scalar_one_or_none()


async def update_user(
    session: AsyncSession, user: dict[str, object], user_id: UUID
) -> User | None:
    result = await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(**user)
        .returning(User)
    )
    updated_user = result.scalar_one_or_none()
    if updated_user is not None:
        logger.info("User updated user_id=%s", user_id)
    return updated_user


async def delete_user(session: AsyncSession, user_id: UUID) -> bool:
    result = await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(status=UserStatus.inactive)
    )
    if result.rowcount:
        logger.info("User deactivated user_id=%s", user_id)
        return True
    return False


async def check_role(session: AsyncSession, user_id: UUID) -> UserRole | None:
    return await session.scalar(select(User.role).where(User.id == user_id))


async def ban_user(session: AsyncSession, user_id: UUID) -> bool:
    result = await session.execute(
        update(User).where(User.id == user_id).values(status=UserStatus.banned)
    )
    if result.rowcount:
        logger.info("User banned user_id=%s", user_id)
        return True
    return False


async def unban_user(session: AsyncSession, user_id: UUID) -> bool:
    result = await session.execute(
        update(User).where(User.id == user_id).values(status=UserStatus.active)
    )
    if result.rowcount:
        logger.info("User unbanned user_id=%s", user_id)
        return True
    return False


async def update_password(
    session: AsyncSession, password: str, user_id: UUID
) -> bool:
    result = await session.execute(
        update(User)
        .where(User.id == user_id, User.status == UserStatus.active)
        .values(password_hash=hash_password(password))
    )
    if result.rowcount:
        logger.info("User password updated user_id=%s", user_id)
        return True
    return False
