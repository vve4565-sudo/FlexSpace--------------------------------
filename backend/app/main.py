from contextlib import asynccontextmanager

from fastapi import FastAPI

from .admin import AdminModels, AdminView
from .api import router as main_router
from .database.db import engine, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(main_router)


admin = AdminView(
    app,
    engine,
)

admin.register_tables(
    tables=[
        AdminModels.UserAdmin,
        AdminModels.RoomAdmin,
        AdminModels.BookingAdmin,
    ]
)
