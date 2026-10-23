from fastapi import APIRouter, Depends, Form, HTTPException, status

from ...crud import room as room_crud
from ...database.db import SessionDep
from ...shemas.room import SRoom
from ..depends import Role, RoleChecker

router = APIRouter(
    tags=["manager"],
    dependencies=[
        Depends(RoleChecker([Role.manager])),
    ],
)


@router.post("/manage_room/new_room", status_code=status.HTTP_201_CREATED)
async def new_room(
    session: SessionDep,
    room: SRoom = Form(),
):

    result = await room_crud.create_room(session, room)
    if result:
        return result

    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


@router.delete("/manage_room/{room_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_room(
    session: SessionDep,
    room_id: int,
):

    await room_crud.delete_room(session, room_id)
    return {"message": "Room deleted"}
