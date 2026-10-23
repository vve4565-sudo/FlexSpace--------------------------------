from datetime import datetime
from decimal import Decimal
from enum import Enum as enum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    MappedAsDataclass,
    mapped_column,
    relationship,
)


class UserRole(str, enum):
    user = "user"
    admin = "admin"
    manager = "manager"


class UserStatus(str, enum):
    active = "active"
    banned = "banned"
    inactive = "inactive"


class RoomType(str, enum):
    private = "private"
    public = "public"


class BookingStatus(str, enum):
    pending = "pending"
    confirmed = "confirmed"
    cancelled = "cancelled"


class Base(MappedAsDataclass, DeclarativeBase):
    id: Mapped[UUID] = mapped_column(
        primary_key=True, init=False, default_factory=uuid4
    )


class User(Base):
    __tablename__ = "users"

    __table_args__ = (Index("ix_users_status_role", "status", "role"),)

    email: Mapped[str] = mapped_column(unique=True, nullable=False)
    password_hash: Mapped[str]
    nickname: Mapped[str]
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"),
        default=UserRole.user,
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status"),
        default=UserStatus.active,
    )
    is_superuser: Mapped[bool] = mapped_column(default=False)

    bookings: Mapped[list[Bookings]] = relationship(back_populates="user", init=False)


class Room(Base):
    __tablename__ = "rooms"

    __table_args__ = (
        CheckConstraint("capacity > 0", name="ck_rooms_capacity_positive"),
        CheckConstraint("cost_per_hour >= 0", name="ck_rooms_cost_nonnegative"),
        Index("ix_rooms_type_capacity_id", "type", "capacity", "id"),
    )

    title: Mapped[str]
    type: Mapped[RoomType] = mapped_column(Enum(RoomType, name="room_type"))

    capacity: Mapped[int]
    cost_per_hour: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    bookings: Mapped[list[Bookings]] = relationship(back_populates="room", init=False)


class Bookings(Base):
    __tablename__ = "bookings"

    __table_args__ = (
        CheckConstraint("end_time > start_time", name="ck_bookings_valid_time"),
        Index(
            "ix_bookings_room_status_time",
            "room_id",
            "status",
            "start_time",
            "end_time",
        ),
        Index("ix_bookings_user_start_time", "user_id", "start_time"),
    )

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    room_id: Mapped[UUID] = mapped_column(ForeignKey("rooms.id"))
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, name="booking_status")
    )
    cost: Mapped[Decimal] = mapped_column(Numeric(10, 2))

    user: Mapped[User] = relationship(back_populates="bookings", init=False)
    room: Mapped[Room] = relationship(back_populates="bookings", init=False)
