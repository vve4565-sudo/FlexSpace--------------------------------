from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SRoom(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    type: Literal["private", "public"]
    capacity: int = Field(gt=0, le=500)
    cost_per_hour: Decimal = Field(ge=0, max_digits=10, decimal_places=2)


class SRoomBase(SRoom):
    id: UUID

    model_config = ConfigDict(from_attributes=True)
