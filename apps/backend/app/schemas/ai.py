from pydantic import BaseModel, Field


class AIVerdict(BaseModel):
    rule_code: str
    entity_key: str
    result: str = Field(pattern="^(pass|fail|needs_review)$")
    severity: str = Field(pattern="^(warning|high|critical)$")
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: dict
    impact_ru: str
    recommendation_ru: str
    reasoning_short_ru: str
