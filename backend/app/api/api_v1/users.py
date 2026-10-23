from typing import Annotated
from uuid import UUID

from authx import TokenPayload
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status

from ...config.security import security
from ...crud import user as crud_user
from ...database.db import SessionDep
from ...shemas.user import SOutputUser, SOutputUserWithBookings, SUserBase

router = APIRouter(
    prefix="/users",
    tags=["users"],
)


@router.get("/me")
async def read_user_me(
    session: SessionDep,
    request: Request,
    token: Annotated[TokenPayload, Depends(security.access_token_required)],
) -> SOutputUserWithBookings:

    user = await crud_user.get_user_by_id(session=session, user_id=UUID(token.sub))
    if user:
        return user  # type: ignore

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")


@router.patch("/me")
async def update_user_me(
    session: SessionDep,
    token: Annotated[TokenPayload, Depends(security.access_token_required)],
    data: Annotated[SUserBase, Form()],
):
    user = await crud_user.get_user_by_id(session=session, user_id=UUID(token.sub))
    if user:
        await crud_user.update_user(
            session=session,
            user=data.model_dump(exclude_unset=True),
            user_id=user.id,
        )
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bad request")


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user_me(
    session: SessionDep,
    token: Annotated[TokenPayload, Depends(security.access_token_required)],
):
    await crud_user.delete_user(session=session, user_id=UUID(token.sub))
    return
