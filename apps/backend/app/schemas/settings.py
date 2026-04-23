from pydantic import BaseModel, Field


class PromptSettingsOut(BaseModel):
    prompt: str


class PromptSettingsUpdateRequest(BaseModel):
    prompt: str = Field(min_length=20, max_length=20000)
