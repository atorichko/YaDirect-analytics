from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_db
from app.repositories.audit_exception import AuditExceptionRepository
from app.schemas.exceptions import AuditExceptionCreateRequest, AuditExceptionOut

router = APIRouter(prefix="/exceptions", tags=["exceptions"])


@router.get("", response_model=list[AuditExceptionOut])
async def list_exceptions(
    _user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
    account_id: Annotated[UUID, Query()],
) -> list[AuditExceptionOut]:
    repo = AuditExceptionRepository(session)
    rows = await repo.list_by_account(account_id)
    return [
        AuditExceptionOut(
            id=row.id,
            account_id=row.account_id,
            rule_code=row.rule_code,
            entity_key=row.entity_key,
            reason=row.reason,
            created_by_user_id=row.created_by_user_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
        for row in rows
    ]


@router.post("", response_model=AuditExceptionOut, status_code=status.HTTP_201_CREATED)
async def create_exception(
    body: AuditExceptionCreateRequest,
    user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AuditExceptionOut:
    repo = AuditExceptionRepository(session)
    try:
        row = await repo.create(
            account_id=body.account_id,
            rule_code=body.rule_code,
            entity_key=body.entity_key,
            reason=body.reason,
            created_by_user_id=user.id,
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Exception with this account/rule/entity already exists",
        ) from exc
    return AuditExceptionOut(
        id=row.id,
        account_id=row.account_id,
        rule_code=row.rule_code,
        entity_key=row.entity_key,
        reason=row.reason,
        created_by_user_id=row.created_by_user_id,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


@router.delete("/{exception_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_exception(
    exception_id: UUID,
    _user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    repo = AuditExceptionRepository(session)
    row = await repo.get_by_id(exception_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exception not found")
    await repo.delete(row)
    await session.commit()
