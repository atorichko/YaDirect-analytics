"""Refresh default ai_analysis_prompt text for installs that still have the short seed.

Revision ID: 20250423_0006
Revises: 20250423_0005
Create Date: 2026-04-23
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20250423_0006"
down_revision: Union[str, Sequence[str], None] = "20250423_0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_SEED = (
    "Проведи аудит рекламной кампании Яндекс Директ и верни структурированные находки: "
    "уровень (L1/L2/L3), severity, краткое объяснение и рекомендацию."
)

_NEW_DEFAULT = (
    "Ты — эксперт по Яндекс Директ и рекламной аналитике. Тебе передают JSON одной сущности (объявление и связанные поля) "
    "и формулировку правила аудита. Нужно оценить, есть ли нарушение именно этого правила для данной сущности.\n\n"
    "Требования к ответу:\n"
    "- Верни строго один JSON-объект по указанной схеме, без Markdown и без текста вокруг.\n"
    "- Поле result: pass — нарушения нет; fail — нарушение явно есть; needs_review — данных недостаточно или граничный случай.\n"
    "- severity: warning | high | critical — по силе последствий для рекламы (критично = остановка показов, модерация, полная потеря трафика).\n"
    "- level в ответе должен соответствовать уровню правила из каталога (L1 / L2 / L3), не выдумывай другой уровень.\n"
    "- evidence — только факты из входных данных (цитаты полей, id, статусы). Не придумывай значения, которых нет во входе.\n"
    "- impact_ru — кратко, по-русски: на что влияет проблема для рекламодателя (трафик, деньги, модерация, отчётность).\n"
    "- recommendation_ru — конкретное действие по исправлению на русском.\n"
    "- reasoning_short_ru — 1–2 предложения, почему выбран такой result.\n"
    "- confidence — число от 0 до 1, насколько уверен вывод при имеющихся данных.\n\n"
    "Если во входе нет данных, необходимых для проверки правила, result=needs_review и объясни это в reasoning_short_ru."
)


def upgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("UPDATE app_settings SET value = :new WHERE key = 'ai_analysis_prompt' AND value = :old"),
        {"new": _NEW_DEFAULT, "old": _OLD_SEED},
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text("UPDATE app_settings SET value = :old WHERE key = 'ai_analysis_prompt' AND value = :new"),
        {"old": _OLD_SEED, "new": _NEW_DEFAULT},
    )
