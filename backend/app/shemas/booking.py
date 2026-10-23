from datetime import datetime, timedelta
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..database.models import BookingStatus


class SBookingCreate(BaseModel):
    start_time: datetime
    end_time: datetime

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.start_time.tzinfo is None or self.end_time.tzinfo is None:
            raise ValueError("Booking times must include a timezone")
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        if self.end_time - self.start_time > timedelta(days=30):
            raise ValueError("Bookings cannot exceed 30 days")
        return self


class SBookingsOutput(BaseModel):
    id: UUID
    room_id: UUID
    start_time: datetime
    end_time: datetime
    status: BookingStatus
    cost: Decimal = Field(ge=0)

    model_config = ConfigDict(from_attributes=True)


class STokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
