import logging
from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from sqlalchemy import desc, exists, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..database.models import Bookings, BookingStatus, Room
from ..shemas.room import SRoom

logger = logging.getLogger(__name__)


class RoomNotFoundError(Exception):
    pass


class RoomHasBookingsError(Exception):
    pass


class BookingConflictError(Exception):
    pass


class BookingNotFoundError(Exception):
    pass


class BookingStateError(Exception):
    pass


async def create_room(session: AsyncSession, room: SRoom) -> Room:
    new_room = Room(**room.model_dump())
    session.add(new_room)
    await session.flush()
    logger.info("Room created room_id=%s", new_room.id)
    return new_room


async def delete_room(session: AsyncSession, room_id: UUID) -> None:
    room = await session.get(Room, room_id, with_for_update=True)
    if room is None:
        raise RoomNotFoundError

    has_bookings = await session.scalar(
        select(
            exists().where(Bookings.room_id == room_id)
        )
    )
    if has_bookings:
        raise RoomHasBookingsError

    await session.delete(room)
    await session.flush()
    logger.info("Room deleted room_id=%s", room_id)


async def get_free_rooms(
    session: AsyncSession,
    room_type: Literal["private", "public"] | None = None,
    capacity: int | None = None,
    page: int = 1,
    page_size: int = 10,
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> list[Room]:
    if (start_time is None) != (end_time is None):
        raise ValueError("Both booking interval boundaries are required")

    query = select(Room)
    if start_time is not None and end_time is not None:
        occupied = exists().where(
            Bookings.room_id == Room.id,
            Bookings.status.in_([BookingStatus.pending, BookingStatus.confirmed]),
            Bookings.start_time < end_time,
            Bookings.end_time > start_time,
        )
        query = query.where(~occupied)

    if room_type is not None:
        query = query.where(Room.type == room_type)
    if capacity is not None:
        query = query.where(Room.capacity >= capacity)

    query = query.order_by(Room.id).offset((page - 1) * page_size).limit(page_size)
    result = await session.execute(query)
    return list(result.scalars().all())


async def book_room(
    session: AsyncSession,
    room_id: UUID,
    user_id: UUID,
    start_time: datetime,
    end_time: datetime,
) -> Bookings:
    if start_time.tzinfo is None or end_time.tzinfo is None:
        raise ValueError("Booking times must include a timezone")
    if end_time <= start_time:
        raise ValueError("end_time must be after start_time")

    room = await session.scalar(
        select(Room).where(Room.id == room_id).with_for_update()
    )
    if room is None:
        raise RoomNotFoundError

    overlapping_booking = await session.scalar(
        select(Bookings.id).where(
            Bookings.room_id == room_id,
            Bookings.status.in_([BookingStatus.pending, BookingStatus.confirmed]),
            Bookings.start_time < end_time,
            Bookings.end_time > start_time,
        ).limit(1)
    )
    if overlapping_booking is not None:
        raise BookingConflictError

    hours = Decimal(str((end_time - start_time).total_seconds())) / Decimal(3600)
    cost = (room.cost_per_hour * hours).quantize(Decimal("0.01"))
    booking = Bookings(
        room_id=room_id,
        user_id=user_id,
        start_time=start_time,
        end_time=end_time,
        status=BookingStatus.pending,
        cost=cost,
    )
    session.add(booking)
    await session.flush()
    logger.info("Booking created booking_id=%s room_id=%s", booking.id, room_id)
    return booking


async def get_user_bookings(
    session: AsyncSession, user_id: UUID
) -> list[Bookings]:
    query = (
        select(Bookings)
        .where(Bookings.user_id == user_id)
        .options(selectinload(Bookings.room))
        .order_by(desc(Bookings.start_time), Bookings.id)
    )
    result = await session.execute(query)
    return list(result.scalars().all())


async def booking_cancel(
    session: AsyncSession, booking_id: UUID, user_id: UUID
) -> None:
    booking = await session.scalar(
        select(Bookings)
        .where(Bookings.id == booking_id, Bookings.user_id == user_id)
        .with_for_update()
    )
    if booking is None:
        raise BookingNotFoundError
    if booking.status is not BookingStatus.pending:
        raise BookingStateError
    booking.status = BookingStatus.cancelled
    await session.flush()
    logger.info("Booking cancelled booking_id=%s", booking_id)


async def booking_confirm(session: AsyncSession, booking_id: UUID) -> None:
    booking = await session.scalar(
        select(Bookings).where(Bookings.id == booking_id).with_for_update()
    )
    if booking is None:
        raise BookingNotFoundError
    if booking.status is not BookingStatus.pending:
        raise BookingStateError
    booking.status = BookingStatus.confirmed
    await session.flush()
    logger.info("Booking confirmed booking_id=%s", booking_id)
