from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import RequireAdmin, get_db
from app.core.ai_prompt_defaults import DEFAULT_AI_ANALYSIS_PROMPT_PREFIX
from app.models.app_setting import AppSetting
from app.schemas.settings import PromptSettingsOut, PromptSettingsUpdateRequest

router = APIRouter(prefix="/settings", tags=["settings"])

PROMPT_KEY = "ai_analysis_prompt"
DEFAULT_PROMPT = DEFAULT_AI_ANALYSIS_PROMPT_PREFIX


@router.get("/ai-prompt", response_model=PromptSettingsOut)
async def get_ai_prompt(
    _admin: RequireAdmin,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PromptSettingsOut:
    row = await session.get(AppSetting, PROMPT_KEY)
    if row is None:
        row = AppSetting(key=PROMPT_KEY, value=DEFAULT_PROMPT)
        session.add(row)
        await session.commit()
        await session.refresh(row)
    return PromptSettingsOut(prompt=row.value)


@router.put("/ai-prompt", response_model=PromptSettingsOut)
async def update_ai_prompt(
    body: PromptSettingsUpdateRequest,
    _admin: RequireAdmin,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> PromptSettingsOut:
    row = await session.get(AppSetting, PROMPT_KEY)
    if row is None:
        row = AppSetting(key=PROMPT_KEY, value=body.prompt)
        session.add(row)
    else:
        row.value = body.prompt
    await session.commit()
    return PromptSettingsOut(prompt=body.prompt)
