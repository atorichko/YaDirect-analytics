from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.services.l1_rules import FindingDraft, _is_active_yandex_campaign


@dataclass(slots=True)
class L2Context:
    account_id: str
    campaigns: list[dict[str, Any]]
    metrika_goals: list[dict[str, Any]] = field(default_factory=list)


L2RuleHandler = Callable[[L2Context, dict[str, Any]], list[FindingDraft]]


def _is_conversion_strategy(strategy: Any) -> bool:
    value = str(strategy or "").lower()
    return "conversion" in value or "конверс" in value or "cpa" in value or "target_cpa" in value


def _metrika_counter_missing(value: Any) -> bool:
    if value is None:
        return True
    s = str(value).strip().lower()
    return s in {"", "none", "null", "0"}


def _goal_is_unavailable(goal: dict[str, Any]) -> bool:
    status = str(goal.get("status") or "").lower()
    access = str(goal.get("access") or "").lower()
    return status in {"deleted", "removed", "archived"} or access in {"revoked", "denied"}


def _campaign_without_metrika_counter(ctx: L2Context, rule: dict[str, Any]) -> list[FindingDraft]:
    """Активная кампания без привязанного счётчика Яндекс Метрики (любая стратегия)."""
    out: list[FindingDraft] = []
    for campaign in ctx.campaigns:
        if not _is_active_yandex_campaign(campaign):
            continue
        if not _metrika_counter_missing(campaign.get("metrika_counter_id")):
            continue
        campaign_id = str(campaign.get("id"))
        out.append(
            FindingDraft(
                entity_key=f"campaign:{campaign_id}:no_metrika_counter",
                issue_location=f"campaign:{campaign_id}",
                campaign_external_id=campaign_id,
                group_external_id=None,
                ad_external_id=None,
                evidence={
                    "campaign_id": campaign_id,
                    "campaign_name": campaign.get("name"),
                    "metrika_counter_id": campaign.get("metrika_counter_id"),
                    "strategy_type": campaign.get("strategy_type"),
                },
                impact_ru="В настройках кампании не подключён счётчик Яндекс Метрики — теряются атрибуция и данные для анализа и оптимизации.",
                recommendation_ru=rule.get("recommendation_ru", "Подключите счётчик Метрики в настройках кампании."),
            )
        )
    return out


def _campaign_without_metrika_goals(ctx: L2Context, rule: dict[str, Any]) -> list[FindingDraft]:
    """Счётчик задан, но цели Метрики к кампании не добавлены."""
    out: list[FindingDraft] = []
    for campaign in ctx.campaigns:
        if not _is_active_yandex_campaign(campaign):
            continue
        if _metrika_counter_missing(campaign.get("metrika_counter_id")):
            continue
        goal_ids = campaign.get("goal_ids")
        if isinstance(goal_ids, list) and len(goal_ids) > 0:
            continue
        campaign_id = str(campaign.get("id"))
        out.append(
            FindingDraft(
                entity_key=f"campaign:{campaign_id}:no_metrika_goals",
                issue_location=f"campaign:{campaign_id}",
                campaign_external_id=campaign_id,
                group_external_id=None,
                ad_external_id=None,
                evidence={
                    "campaign_id": campaign_id,
                    "campaign_name": campaign.get("name"),
                    "metrika_counter_id": campaign.get("metrika_counter_id"),
                    "goal_ids": goal_ids if isinstance(goal_ids, list) else [],
                },
                impact_ru="Цели Яндекс Метрики не добавлены в кампанию — неполные данные по конверсиям и ограниченные возможности отчётности.",
                recommendation_ru=rule.get(
                    "recommendation_ru",
                    "Добавьте в кампанию цели Метрики, соответствующие вашим KPI.",
                ),
            )
        )
    return out


def _conversion_strategy_without_metrika(ctx: L2Context, rule: dict[str, Any]) -> list[FindingDraft]:
    out: list[FindingDraft] = []
    for campaign in ctx.campaigns:
        if not _is_conversion_strategy(campaign.get("strategy_type")):
            continue
        if not _metrika_counter_missing(campaign.get("metrika_counter_id")):
            continue
        campaign_id = str(campaign.get("id"))
        out.append(
            FindingDraft(
                entity_key=f"campaign:{campaign_id}:no_metrika",
                issue_location=f"campaign:{campaign_id}",
                campaign_external_id=campaign_id,
                group_external_id=None,
                ad_external_id=None,
                evidence={
                    "campaign_id": campaign_id,
                    "strategy_type": campaign.get("strategy_type"),
                    "metrika_counter_id": campaign.get("metrika_counter_id"),
                },
                impact_ru="Конверсионная стратегия без привязки к Метрике не может корректно оптимизироваться.",
                recommendation_ru=rule.get("recommendation_ru", "Подключить счётчик Метрики к кампании."),
            )
        )
    return out


def _conversion_strategy_without_goal(ctx: L2Context, rule: dict[str, Any]) -> list[FindingDraft]:
    out: list[FindingDraft] = []
    for campaign in ctx.campaigns:
        if not _is_conversion_strategy(campaign.get("strategy_type")):
            continue
        goal_ids = campaign.get("goal_ids")
        if isinstance(goal_ids, list) and len(goal_ids) > 0:
            continue
        campaign_id = str(campaign.get("id"))
        out.append(
            FindingDraft(
                entity_key=f"campaign:{campaign_id}:no_goal",
                issue_location=f"campaign:{campaign_id}",
                campaign_external_id=campaign_id,
                group_external_id=None,
                ad_external_id=None,
                evidence={
                    "campaign_id": campaign_id,
                    "strategy_type": campaign.get("strategy_type"),
                    "goal_ids": goal_ids if isinstance(goal_ids, list) else [],
                },
                impact_ru="Конверсионная стратегия без цели не имеет сигнала для обучения.",
                recommendation_ru=rule.get("recommendation_ru", "Задайте цель Метрики для кампании."),
            )
        )
    return out


def _conversion_strategy_with_unavailable_goal(ctx: L2Context, rule: dict[str, Any]) -> list[FindingDraft]:
    if not ctx.metrika_goals:
        return []
    goals_by_id: dict[str, dict[str, Any]] = {}
    for g in ctx.metrika_goals:
        if not isinstance(g, dict):
            continue
        gid = str(g.get("goal_id") or g.get("id") or "")
        if gid:
            goals_by_id[gid] = g
    out: list[FindingDraft] = []
    for campaign in ctx.campaigns:
        if not _is_conversion_strategy(campaign.get("strategy_type")):
            continue
        goal_ids = campaign.get("goal_ids")
        if not isinstance(goal_ids, list) or not goal_ids:
            continue
        bad: list[dict[str, Any]] = []
        for gid in goal_ids:
            key = str(gid)
            row = goals_by_id.get(key)
            if row is None:
                bad.append({"goal_id": key, "reason": "not_found_in_metrika"})
            elif _goal_is_unavailable(row):
                bad.append({"goal_id": key, "status": row.get("status"), "access": row.get("access")})
        if not bad:
            continue
        campaign_id = str(campaign.get("id"))
        first = bad[0]
        ev: dict[str, Any] = {
            "campaign_id": campaign_id,
            "problem_goals": bad,
            "check_logic_ru": (
                "Для кампании с конверсионной стратегией перебираем campaign.goal_ids. "
                "Каждый id сопоставляем со снимком целей Метрики (metrika_goals по goal_id/id): "
                "если цели нет в снимке — reason not_found_in_metrika; если запись есть, "
                "но status в deleted/removed/archived или access в revoked/denied — цель считается недоступной. "
                "Если хотя бы одна из настроенных целей не найдена или недоступна, формируется эта находка."
            ),
        }
        gid = str(first.get("goal_id") or "")
        if gid:
            ev["goal_id"] = gid
        if first.get("status") is not None:
            ev["goal_status"] = first.get("status")
        if first.get("access") is not None:
            ev["goal_access"] = first.get("access")
        out.append(
            FindingDraft(
                entity_key=f"campaign:{campaign_id}:unavailable_goal",
                issue_location=f"campaign:{campaign_id}",
                campaign_external_id=campaign_id,
                group_external_id=None,
                ad_external_id=None,
                evidence=ev,
                impact_ru="В конверсионной стратегии указана недоступная или удалённая цель Метрики.",
                recommendation_ru=rule.get("recommendation_ru", "Выберите активную цель или восстановите доступ."),
            )
        )
    return out


def _conversion_strategy_without_learning_data(ctx: L2Context, rule: dict[str, Any]) -> list[FindingDraft]:
    min_required = int(rule.get("min_conversions_for_learning") or 30)
    output: list[FindingDraft] = []
    for campaign in ctx.campaigns:
        strategy_type = campaign.get("strategy_type")
        if not _is_conversion_strategy(strategy_type):
            continue
        stats = campaign.get("stats") or {}
        conversions = float(stats.get("conversions") or 0)
        if conversions >= min_required:
            continue
        campaign_id = str(campaign.get("id"))
        output.append(
            FindingDraft(
                entity_key=f"campaign:{campaign_id}:learning",
                issue_location=f"campaign:{campaign_id}",
                campaign_external_id=campaign_id,
                group_external_id=None,
                ad_external_id=None,
                evidence={
                    "campaign_id": campaign_id,
                    "strategy_type": strategy_type,
                    "conversions": conversions,
                    "required_min_conversions": min_required,
                    "analysis_period_days": stats.get("analysis_period_days"),
                    "check_logic_ru": (
                        "Берём кампании, у которых strategy_type относится к конверсионным стратегиям. "
                        "Сравниваем stats.conversions (число конверсий за окно stats.analysis_period_days из снимка) "
                        f"с порогом min_conversions_for_learning из правила (здесь {min_required}). "
                        "Если conversions строго меньше порога — находка: для обучения стратегии не хватает статистики."
                    ),
                },
                impact_ru="Стратегия по конверсиям не обучается стабильно из-за нехватки данных.",
                recommendation_ru=rule.get("recommendation_ru", "Сменить стратегию или накопить больше конверсий."),
            )
        )
    return output


def _campaign_chronic_budget_limit(ctx: L2Context, rule: dict[str, Any]) -> list[FindingDraft]:
    threshold_days = int(rule.get("budget_limited_days_threshold") or 3)
    output: list[FindingDraft] = []
    for campaign in ctx.campaigns:
        stats = campaign.get("stats") or {}
        budget_limited_days = int(stats.get("budget_limited_days") or 0)
        if budget_limited_days < threshold_days:
            continue
        campaign_id = str(campaign.get("id"))
        output.append(
            FindingDraft(
                entity_key=f"campaign:{campaign_id}:budget_limit",
                issue_location=f"campaign:{campaign_id}",
                campaign_external_id=campaign_id,
                group_external_id=None,
                ad_external_id=None,
                evidence={
                    "campaign_id": campaign_id,
                    "analysis_period_days": stats.get("analysis_period_days"),
                    "budget_limited_days": budget_limited_days,
                    "avg_hour_of_budget_exhaustion": stats.get("avg_hour_of_budget_exhaustion"),
                    "threshold_days": threshold_days,
                    "check_logic_ru": (
                        "Сравниваем stats.budget_limited_days (сколько дней в окне stats.analysis_period_days "
                        "кампания была ограничена по бюджету) с порогом budget_limited_days_threshold из правила "
                        f"(здесь {threshold_days}). Если budget_limited_days ≥ порога — находка: кампания системно "
                        "упирается в бюджет и недополучает показы."
                    ),
                },
                impact_ru="Кампания регулярно упирается в бюджет и теряет потенциальный трафик.",
                recommendation_ru=rule.get("recommendation_ru", "Увеличить бюджет или перераспределить трафик."),
            )
        )
    return output


def build_l2_rule_registry() -> dict[str, L2RuleHandler]:
    return {
        "CAMPAIGN_WITHOUT_METRIKA_COUNTER": _campaign_without_metrika_counter,
        "CAMPAIGN_WITHOUT_METRIKA_GOALS": _campaign_without_metrika_goals,
        "CONVERSION_STRATEGY_WITHOUT_METRIKA": _conversion_strategy_without_metrika,
        "CONVERSION_STRATEGY_WITHOUT_GOAL": _conversion_strategy_without_goal,
        "CONVERSION_STRATEGY_WITH_UNAVAILABLE_GOAL": _conversion_strategy_with_unavailable_goal,
        "CONVERSION_STRATEGY_WITHOUT_LEARNING_DATA": _conversion_strategy_without_learning_data,
        "CAMPAIGN_CHRONIC_BUDGET_LIMIT": _campaign_chronic_budget_limit,
    }
