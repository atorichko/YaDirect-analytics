from __future__ import annotations

import json
import time
from dataclasses import dataclass

from openai import OpenAI

from app.core.config import settings
from app.schemas.ai import AIVerdict


@dataclass(slots=True)
class PolzaAIResult:
    verdict: AIVerdict
    prompt: str
    raw_response: str
    latency_ms: int
    model: str


class PolzaAIClient:
    def __init__(self) -> None:
        self._client = OpenAI(base_url=settings.polza_ai_base_url, api_key=settings.polza_ai_api_key)
        self._model = settings.ai_model

    def evaluate(self, *, prompt: str) -> PolzaAIResult:
        started = time.perf_counter()
        response = self._client.chat.completions.create(
            model=self._model,
            temperature=0.1,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ты аудитор Яндекс Директ. Верни только JSON по заданной схеме без markdown и комментариев."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        latency_ms = int((time.perf_counter() - started) * 1000)
        text = response.choices[0].message.content or "{}"
        payload = json.loads(text)
        verdict = AIVerdict.model_validate(payload)
        return PolzaAIResult(
            verdict=verdict,
            prompt=prompt,
            raw_response=text,
            latency_ms=latency_ms,
            model=self._model,
        )
