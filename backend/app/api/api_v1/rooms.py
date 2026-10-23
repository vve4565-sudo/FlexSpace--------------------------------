import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import TypeAdapter
from redis.exceptions import RedisError

from ...config.config import settings
from ...crud import room as room_crud
from ...database.db import SessionDep
from ...redis_client import redis
from ...shemas.booking import SBookingCreate, SBookingsOutput
from ...shemas.room import SRoomBase
from ...shemas.user import SOutputUser
from ...utils.email import generate_koworking_template, send_email
from ..depends import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/rooms", tags=["rooms"])
room_adapter = TypeAdapter(list[SRoomBase])


@router.get("/", response_model=list[SRoomBase])
async def get_rooms(
    session: SessionDep,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    filter_by_type: Literal["private", "public"] | None = None,
    filter_by_capacity: int | None = Query(default=None, ge=1),
    start_time: datetime | None = None,
    end_time: datetime | None = None,
) -> list[SRoomBase]:
    if (start_time is None) != (end_time is None):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Both start_time and end_time are required for availability search",
        )
    if start_time is not None and end_time is not None:
        if start_time.tzinfo is None or end_time.tzinfo is None or end_time <= start_time:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A valid timezone-aware interval is required",
            )

    cache_key_data = json.dumps(
        [
            page,
            page_size,
            filter_by_type,
            filter_by_capacity,
            start_time.isoformat() if start_time else None,
            end_time.isoformat() if end_time else None,
        ],
        separators=(",", ":"),
    )
    cache_key_hash = hashlib.sha256(cache_key_data.encode("utf-8")).hexdigest()
    try:
        version = await redis.get("rooms:cache-version") or "0"
        cached_rooms = await redis.get(f"rooms:v{version}:{cache_key_hash}")
        if cached_rooms is not None:
            return [SRoomBase.model_validate(room) for room in json.loads(cached_rooms)]
    except (RedisError, ValueError) as error:
        logger.exception("Room listing cache unavailable or invalid")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Room listing is temporarily unavailable",
        ) from error

    rooms = await room_crud.get_free_rooms(
        session=session,
        room_type=filter_by_type,
        capacity=filter_by_capacity,
        page=page,
        page_size=page_size,
        start_time=start_time.astimezone(timezone.utc) if start_time else None,
        end_time=end_time.astimezone(timezone.utc) if end_time else None,
    )
    response = room_adapter.validate_python(rooms)
    serialized = room_adapter.dump_json(response).decode("utf-8")
    try:
        await redis.set(f"rooms:v{version}:{cache_key_hash}", serialized, ex=60)
    except RedisError as error:
        logger.exception("Unable to cache room listing")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Room listing is temporarily unavailable",
        ) from error
    return response


@router.post(
    "/booking/{room_id}",
    status_code=status.HTTP_201_CREATED,
    response_model=SBookingsOutput,
)
async def booking_room(
    room_id: UUID,
    booking: SBookingCreate,
    session: SessionDep,
    background_tasks: BackgroundTasks,
    user: SOutputUser = Depends(get_current_user),
) -> SBookingsOutput:
    try:
        result = await room_crud.book_room(
            session=session,
            room_id=room_id,
            user_id=user.id,
            start_time=booking.start_time.astimezone(timezone.utc),
            end_time=booking.end_time.astimezone(timezone.utc),
        )
    except room_crud.RoomNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Room not found"
        ) from error
    except room_crud.BookingConflictError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Room is already booked for this time interval",
        ) from error

    try:
        await redis.incr("rooms:cache-version")
    except RedisError as error:
        logger.exception("Unable to invalidate room availability cache")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Booking is temporarily unavailable",
        ) from error

    if settings.emails_enabled:
        background_tasks.add_task(
            send_email,
            user.email,
            "Booking request received",
            generate_koworking_template(
                booking.start_time.strftime("%d/%m/%Y, %H:%M %Z"),
                booking.end_time.strftime("%d/%m/%Y, %H:%M %Z"),
            ),
        )
    else:
        logger.warning("Booking confirmation email was not scheduled: email is disabled")
    return result


@router.get("/bookings/my", response_model=list[SBookingsOutput])
async def my_bookings(
    session: SessionDep,
    user: SOutputUser = Depends(get_current_user),
) -> list[SBookingsOutput]:
    return await room_crud.get_user_bookings(session=session, user_id=user.id)


@router.delete(
    "/bookings/{booking_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def cancel_booking(
    booking_id: UUID,
    session: SessionDep,
    user: SOutputUser = Depends(get_current_user),
) -> None:
    try:
        await room_crud.booking_cancel(session, booking_id, user.id)
    except room_crud.BookingNotFoundError as error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Booking not found"
        ) from error
    except room_crud.BookingStateError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending bookings can be cancelled",
        ) from error
    try:
        await redis.incr("rooms:cache-version")
    except RedisError as error:
        logger.exception("Unable to invalidate room availability cache")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Booking cancellation is temporarily unavailable",
        ) from error
