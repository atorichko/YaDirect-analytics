from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.schemas.auth import LoginRequest, RefreshRequest, TokenPairResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenPairResponse)
async def login(
    body: LoginRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TokenPairResponse:
    service = AuthService(session)
    try:
        return await service.login(body.email, body.password)
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        ) from None


@router.post("/refresh", response_model=TokenPairResponse)
async def refresh_token(
    body: RefreshRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> TokenPairResponse:
    service = AuthService(session)
    try:
        return await service.refresh(body.refresh_token)
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        ) from None
