import pytest
from pydantic import ValidationError

from app.schemas.ai import AIVerdict


def test_ai_verdict_valid() -> None:
    row = AIVerdict.model_validate(
        {
            "rule_code": "GEO_TEXT_TARGETING_MISMATCH",
            "entity_key": "ad:1",
            "result": "needs_review",
            "severity": "high",
            "confidence": 0.74,
            "evidence": {"geo": "msk"},
            "impact_ru": "Влияет на релевантность.",
            "recommendation_ru": "Проверить гео.",
            "reasoning_short_ru": "Текст и таргетинг расходятся.",
        }
    )
    assert row.severity == "high"


def test_ai_verdict_invalid_result() -> None:
    with pytest.raises(ValidationError):
        AIVerdict.model_validate(
            {
                "rule_code": "X",
                "entity_key": "ad:1",
                "result": "unknown",
                "severity": "high",
                "confidence": 0.5,
                "evidence": {},
                "impact_ru": "x",
                "recommendation_ru": "y",
                "reasoning_short_ru": "z",
            }
        )
