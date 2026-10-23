from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from app.api import depends as api_depends
from app.api.api_v1 import auth as auth_module
from app.api.api_v1 import rooms as rooms_module
from app.config.security import hash_password
from app.crud import room as room_crud
from app.crud import user as user_crud
from app.database.models import BookingStatus
from app.main import app
from fastapi.testclient import TestClient


class FakeRedis:
    def __init__(self):
        self.store = {}

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.store:
            return None
        self.store[key] = value
        return True

    async def sadd(self, key, value):
        bucket = self.store.setdefault(key, set())
        if not isinstance(bucket, set):
            bucket = {bucket}
        bucket.add(value)
        self.store[key] = bucket
        return 1

    async def expire(self, key, ttl):
        return True

    async def get(self, key):
        return self.store.get(key)

    async def getdel(self, key):
        value = self.store.pop(key, None)
        return value

    async def delete(self, *keys):
        for key in keys:
            self.store.pop(key, None)
        return len(keys)

    async def smembers(self, key):
        return self.store.get(key, set())

    async def srem(self, key, *values):
        bucket = self.store.get(key, set())
        if isinstance(bucket, set):
            for value in values:
                bucket.discard(value)
            self.store[key] = bucket
        return 1

    async def eval(self, script, numkeys, *args):
        return 1


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def fake_user():
    return SimpleNamespace(
        id=UUID("11111111-1111-1111-1111-111111111111"),
        email="user@example.com",
        password_hash=hash_password("StrongPassword123!"),
        role="user",
        status="active",
        is_superuser=False,
    )


@pytest.fixture
def mock_auth_dependencies(monkeypatch, fake_user):
    fake_redis = FakeRedis()
    monkeypatch.setattr(auth_module, "redis", fake_redis)
    monkeypatch.setattr(user_crud, "get_user_by_email", lambda session, email: None)
    monkeypatch.setattr(
        user_crud,
        "create_user",
        lambda session, user: SimpleNamespace(
            id=UUID("22222222-2222-2222-2222-222222222222"),
            email=user.email,
            password_hash=hash_password(user.password),
            role="user",
            status="active",
            is_superuser=False,
        ),
    )
    monkeypatch.setattr(
        user_crud,
        "update_password",
        lambda session, password, user_id=None, email=None: True,
    )
    return fake_redis


@pytest.fixture
def mock_room_dependencies(monkeypatch, fake_user):
    fake_redis = FakeRedis()
    monkeypatch.setattr(rooms_module, "redis", fake_redis)
    monkeypatch.setattr(
        room_crud,
        "get_free_rooms",
        lambda **kwargs: [
            SimpleNamespace(
                id=UUID("33333333-3333-3333-3333-333333333333"),
                title="Room 1",
                type="private",
                capacity=10,
                cost_per_hour=Decimal("25.00"),
            )
        ],
    )
    monkeypatch.setattr(
        room_crud,
        "book_room",
        lambda **kwargs: SimpleNamespace(
            id=UUID("44444444-4444-4444-4444-444444444444"),
            room_id=kwargs["room_id"],
            user_id=kwargs["user_id"],
            start_time=kwargs["start_time"],
            end_time=kwargs["end_time"],
            status=BookingStatus.pending,
            cost=Decimal("25.00"),
        ),
    )
    monkeypatch.setattr(
        room_crud,
        "get_user_bookings",
        lambda **kwargs: [
            SimpleNamespace(
                id=UUID("55555555-5555-5555-5555-555555555555"),
                room_id=UUID("33333333-3333-3333-3333-333333333333"),
                user_id=kwargs["user_id"],
                start_time=datetime(2026, 10, 25, 10, 0, tzinfo=UTC),
                end_time=datetime(2026, 10, 25, 11, 0, tzinfo=UTC),
                status=BookingStatus.pending,
                cost=Decimal("25.00"),
                room=SimpleNamespace(
                    id=UUID("33333333-3333-3333-3333-333333333333"),
                    title="Room 1",
                    type="private",
                    capacity=10,
                    cost_per_hour=Decimal("25.00"),
                ),
            )
        ],
    )
    app.dependency_overrides[api_depends.get_current_user] = lambda: fake_user
    return fake_redis


def test_registration_returns_tokens(client, mock_auth_dependencies):
    response = client.post(
        "/api/v1/auth/registration",
        data={
            "email": "new@example.com",
            "nickname": "Alice",
            "password": "StrongPassword123!",
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert "access_token" in payload
    assert payload["token_type"] == "bearer"


def test_login_returns_tokens(client, monkeypatch, fake_user):
    fake_redis = FakeRedis()
    monkeypatch.setattr(auth_module, "redis", fake_redis)
    one_user = SimpleNamespace(
        id=fake_user.id,
        email=fake_user.email,
        password_hash=hash_password("StrongPassword123!"),
        status="active",
        is_superuser=False,
    )
    monkeypatch.setattr(user_crud, "get_user_by_email", lambda session, email: one_user)
    client.app.dependency_overrides = {}

    response = client.post(
        "/api/v1/auth/login",
        data={"email": fake_user.email, "password": "StrongPassword123!"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert "access_token" in payload
    assert payload["token_type"] == "bearer"


def test_get_rooms_returns_list(client, mock_room_dependencies):
    response = client.get("/api/v1/rooms/?page=1&page_size=10")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert payload[0]["title"] == "Room 1"


def test_booking_room_creates_booking(client, mock_room_dependencies):
    start = datetime(2026, 10, 25, 10, 0, tzinfo=UTC)
    end = start + timedelta(hours=1)

    response = client.post(
        "/api/v1/rooms/booking/33333333-3333-3333-3333-333333333333",
        json={
            "start_time": start.isoformat(),
            "end_time": end.isoformat(),
        },
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["room_id"] == "33333333-3333-3333-3333-333333333333"
    assert payload["status"] == "pending"


def test_my_bookings_returns_user_bookings(client, mock_room_dependencies):
    response = client.get("/api/v1/rooms/bookings/my")

    assert response.status_code == 200
    payload = response.json()
    assert isinstance(payload, list)
    assert payload[0]["status"] == "pending"


@pytest.fixture(autouse=True)
def clear_dependency_overrides():
    yield
    app.dependency_overrides.clear()
