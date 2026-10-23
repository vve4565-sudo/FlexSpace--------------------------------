from collections.abc import AsyncGenerator
import logging
from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from ..config.config import settings
from ..config.security import hash_password
from .models import User, UserStatus

logger = logging.getLogger(__name__)

engine = create_async_engine(str(settings.SQLALCHEMY_DATABASE_URI))
session = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with session() as db_session:
        try:
            yield db_session
            await db_session.commit()
        except Exception:
            await db_session.rollback()
            logger.exception("Request database transaction rolled back")
            raise


SessionDep = Annotated[AsyncSession, Depends(get_session)]


async def init_db() -> None:

    async with session.begin() as s:
        user = await s.execute(
            select(User).where(User.email == settings.FIRST_SUPERUSER)
        )

        if not user.scalar_one_or_none():
            user = User(
                email=settings.FIRST_SUPERUSER,
                password_hash=hash_password(settings.FIRST_SUPERUSER_PASSWORD),
                nickname=settings.FIRST_SUPERUSER_FULLNAME,
                role=settings.FIRST_SUPERUSER_ROLE,  # type: ignore
                status=UserStatus.active,
                is_superuser=True,
            )
            s.add(user)
            logger.info("Initial administrator account created")
