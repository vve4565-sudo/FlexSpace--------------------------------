from fastapi import APIRouter, Depends, Form
from fastapi.security import HTTPBearer

from ...crud import user as crud_user
from ...database.db import SessionDep
from ...shemas.user import SUserRole
from ..depends import Role, RoleChecker

router = APIRouter(
    tags=["admin"],
    dependencies=[
        Depends(RoleChecker([Role.admin])),
    ],
)


@router.post("/user/{user_id}/ban")
async def ban_user_by_id(
    session: SessionDep,
    user_id: int,
):

    await crud_user.ban_user(session=session, user_id=user_id)
    return {"message": "User banned"}


@router.post("/user/{user_id}/unban")
async def unban_user_by_id(
    session: SessionDep,
    user_id: int,
):

    await crud_user.unban_user(session=session, user_id=user_id)
    return {"message": "User unbanned"}


@router.post("/promote/{user_id}")
async def promote_user(
    session: SessionDep,
    user_id: int,
    user_role: SUserRole = Form(),
):

    await crud_user.update_user(
        session=session,
        user_id=user_id,
        user=user_role.model_dump(exclude_unset=True),
    )
    return {"message": "User promoted"}
