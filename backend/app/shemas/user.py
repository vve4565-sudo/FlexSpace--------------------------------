from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .booking import SBookingsOutput


class SUser(BaseModel):
    email: EmailStr


class SUserBase(SUser):
    nickname: str


class SUserCreate(SUserBase):
    password: str = Field(min_length=12, max_length=128)


class SUserLogin(SUser):
    password: str = Field(min_length=1, max_length=128)


class SUserUpdate(BaseModel):
    email: EmailStr | None = None
    nickname: str | None = Field(default=None, min_length=1, max_length=120)


class SOutputUserWithBookings(BaseModel):
    id: UUID
    email: EmailStr
    nickname: str
    role: Literal["user", "admin", "manager"]
    status: Literal["active", "banned", "inactive"]
    is_superuser: bool
    bookings: list[SBookingsOutput] | None = None

    model_config = ConfigDict(from_attributes=True)


class SOutputUser(BaseModel):
    id: UUID
    email: EmailStr
    nickname: str
    role: Literal["user", "admin", "manager"]
    status: Literal["active", "banned", "inactive"]
    is_superuser: bool

    model_config = ConfigDict(from_attributes=True)


class SUserRole(BaseModel):
    role: Literal["user", "manager", "admin"]
