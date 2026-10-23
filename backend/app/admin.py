from fastapi import Request
from fastapi.datastructures import State
from sqladmin import Admin, ModelView

from .config.security import hash_password
from .database.models import Bookings, Room, User


class AdminModels:
    class UserAdmin(ModelView, model=User):
        column_list = [
            User.id,
            User.email,
            User.nickname,
            User.role,
            User.status,
            User.is_superuser,
        ]

        searchable_columns = [
            User.id,
            User.nickname,
            User.email,
        ]

        form_edit_rules = ["id", "email", "nickname", "role", "status", "password_hash"]

        column_labels = {User.password_hash: "password"}

        async def on_model_change(
            self,
            data: dict,
            model: User,
            is_created: bool,
            request: Request[State],
        ) -> None:

            data["password_hash"] = hash_password(data["password_hash"])
            return await super().on_model_change(data, model, is_created, request)

    class RoomAdmin(ModelView, model=Room):
        column_list = [
            Room.id,
            Room.title,
            Room.type,
            Room.capacity,
            Room.cost_per_hour,
        ]

        searchable_columns = [
            Room.id,
            Room.title,
            Room.type,
            Room.capacity,
            Room.cost_per_hour,
        ]

        form_edit_rules = [
            "title",
            "type",
            "capacity",
            "cost_per_hour",
        ]

    class BookingAdmin(ModelView, model=Bookings):
        column_list = [
            Bookings.id,
            Bookings.room_id,
            Bookings.user_id,
            Bookings.start_time,
            Bookings.end_time,
            Bookings.status,
        ]

        searchable_columns = [
            Bookings.id,
            Bookings.room_id,
            Bookings.user_id,
            Bookings.start_time,
            Bookings.end_time,
            Bookings.status,
        ]
        can_delete = False
        can_create = False
        can_edit = False


class AdminView(Admin):
    def register_tables(self, tables: list[type[ModelView]]):
        [self.add_view(table) for table in tables]
