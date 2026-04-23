from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class L1Context:
    account_id: str
    campaigns: list[dict[str, Any]]
    groups: list[dict[str, Any]]
    ads: list[dict[str, Any]]
    keywords: list[dict[str, Any]]
    extensions: list[dict[str, Any]]


@dataclass(slots=True)
class FindingDraft:
    entity_key: str
    issue_location: str
    campaign_external_id: str | None
    group_external_id: str | None
    ad_external_id: str | None
    evidence: dict[str, Any]
    impact_ru: str
    recommendation_ru: str


RuleHandler = Callable[[L1Context, dict[str, Any]], list[FindingDraft]]


def _is_active(value: Any) -> bool:
    return str(value or "").lower() in {"active", "on", "enabled"}


def _is_active_yandex_campaign(campaign: dict[str, Any]) -> bool:
    """Direct API stores campaign serving state in `State` (mapped to `status` in snapshots)."""
    st = str(campaign.get("status") or campaign.get("state") or "").lower()
    return st in {"on", "active", "enabled", "yes", "converted"}


def _is_servable_ad_group(group: dict[str, Any]) -> bool:
    """
    Yandex Direct AdGroup moderation `Status`: ACCEPTED / PREACCEPTED mean the group can serve;
    DRAFT / MODERATION / REJECTED do not. Fixture data uses active/paused.
    """
    raw = str(group.get("status") or "").strip().lower()
    if raw in {"accepted", "preaccepted"}:
        return True
    if raw in {"draft", "moderation", "premoderation", "rejected"}:
        return False
    return _is_active(group.get("status"))


def _is_servable_yandex_ad(ad: dict[str, Any]) -> bool:
    """Ads use `State` (ON/OFF/…) and `Status` (ACCEPTED/…) in API v5."""
    state = str(ad.get("state") or "").strip().lower()
    if state in {"off", "suspended", "archived", "deleted"}:
        return False
    if state in {"on", "yes", "active", "enabled"}:
        return True
    status = str(ad.get("status") or "").strip().lower()
    if status in {"accepted"}:
        return True
    return _is_active(ad.get("status")) or _is_active(ad.get("state"))


def _is_servable_yandex_keyword(keyword: dict[str, Any]) -> bool:
    state = str(keyword.get("state") or "").strip().lower()
    if state in {"off", "suspended", "archived", "deleted"}:
        return False
    if state in {"on", "yes", "active", "enabled"}:
        return True
    status = str(keyword.get("status") or "").strip().lower()
    if status in {"accepted"}:
        return True
    return _is_active(keyword.get("status")) or _is_active(keyword.get("state"))


def _normalize_keyword(text: str) -> str:
    raw_tokens = [item for item in str(text).lower().split() if item]
    positive: list[str] = []
    negative: list[str] = []
    for token in raw_tokens:
        is_minus = token.startswith("-")
        cleaned = re.sub(r"[^\wа-яА-Я0-9]", "", token[1:] if is_minus else token)
        if not cleaned:
            continue
        if is_minus:
            negative.append(cleaned)
        else:
            positive.append(cleaned)
    pos = " ".join(positive)
    if not negative:
        return pos
    return f"{pos} || -" + ",".join(sorted(set(negative)))


def _keyword_positive_tokens(text: str) -> set[str]:
    raw_tokens = [item for item in str(text).lower().split() if item]
    out: set[str] = set()
    for token in raw_tokens:
        if token.startswith("-"):
            continue
        cleaned = re.sub(r"[^\wа-яА-Я0-9]", "", token)
        if cleaned:
            out.add(cleaned)
    return out


def _negative_tokens(items: Any) -> set[str]:
    if not isinstance(items, list):
        return set()
    out: set[str] = set()
    for item in items:
        token = str(item or "").strip().lstrip("-").lower()
        token = re.sub(r"[^\wа-яА-Я0-9]", "", token)
        if token:
            out.add(token)
    return out


def _geo_setting_tokens(geo_list: Any) -> set[str]:
    """Normalized tokens from campaign geo settings (names, region labels in snapshots)."""
    if not isinstance(geo_list, list):
        return set()
    out: set[str] = set()
    for item in geo_list:
        s = str(item).lower()
        for part in re.split(r"[^\wа-яА-Я0-9]+", s):
            t = re.sub(r"[^\wа-яА-Я0-9]", "", part)
            if len(t) >= 2:
                out.add(t)
    return out


def _campaign_geo_overlaps_campaign_negatives(ctx: L1Context, rule: dict[str, Any]) -> list[FindingDraft]:
    """Минус-слова кампании совпадают с токенами геотаргетинга (или вхождение в строку гео)."""
    out: list[FindingDraft] = []
    for campaign in ctx.campaigns:
        if not _is_active_yandex_campaign(campaign):
            continue
        geo = campaign.get("geo") or []
        negatives = _negative_tokens(campaign.get("negative_keywords"))
        if not negatives:
            continue
        geo_tokens = _geo_setting_tokens(geo)
        geo_strings = [str(g).lower() for g in geo] if isinstance(geo, list) else []
        overlap = set(geo_tokens) & negatives
        for n in negatives:
            if len(n) < 2:
                continue
            for gs in geo_strings:
                compact = re.sub(r"[^\wа-яА-Я0-9]+", "", gs)
                if n in gs or (compact and n in compact):
                    overlap.add(n)
                    break
        if not overlap:
            continue
        campaign_id = str(campaign.get("id"))
        out.append(
            FindingDraft(
                entity_key=f"campaign:{campaign_id}:geo_negative_overlap",
                issue_location=f"campaign:{campaign_id}",
                campaign_external_id=campaign_id,
                group_external_id=None,
                ad_external_id=None,
                evidence={
                    "campaign_id": campaign_id,
                    "campaign_name": campaign.get("name"),
                    "campaign_geo": geo,
                    "overlap_tokens": sorted(overlap),
                },
                impact_ru="Минус-слова кампании пересекаются с настройками геотаргетинга: часть целевой аудитории может быть отсечена или логика противоречит сама себе.",
                recommendation_ru=rule.get(
                    "recommendation_ru",
                    "Уберите конфликтующие минус-слова или скорректируйте геотаргетинг.",
                ),
            )
        )
    return out


def _active_campaign_without_active_groups(ctx: L1Context, rule: dict[str, Any]) -> list[FindingDraft]:
    groups_by_campaign: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for group in ctx.groups:
        groups_by_campaign[str(group.get("campaign_id"))].append(group)

    output: list[FindingDraft] = []
    for campaign in ctx.campaigns:
        if not _is_active_yandex_campaign(campaign):
            continue
        campaign_id = str(campaign.get("id"))
        campaign_groups = groups_by_campaign.get(campaign_id, [])
        active_groups = [g for g in campaign_groups if _is_servable_ad_group(g)]
        if active_groups:
            continue
        output.append(
            FindingDraft(
                entity_key=f"campaign:{campaign_id}",
                issue_location=f"campaign:{campaign_id}",
                campaign_external_id=campaign_id,
                group_external_id=None,
                ad_external_id=None,
                evidence={
                    "campaign_id": campaign_id,
                    "campaign_name": campaign.get("name"),
                    "active_group_count": 0,
                    "groups_in_snapshot": [
                        {
                            "group_id": g.get("id"),
                            "group_name": g.get("name"),
                            "status": g.get("status"),
                            "serving_status": g.get("serving_status"),
                        }
                        for g in campaign_groups
                    ],
                },
                impact_ru="Кампания активна, но показы фактически не работают из-за отсутствия активных групп.",
                recommendation_ru=rule.get("recommendation_ru", "Остановить кампанию или добавить рабочие группы."),
            )
        )
    return output


def _active_group_without_active_ads(ctx: L1Context, rule: dict[str, Any]) -> list[FindingDraft]:
    ads_by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ad in ctx.ads:
        ads_by_group[str(ad.get("ad_group_id"))].append(ad)

    output: list[FindingDraft] = []
    for group in ctx.groups:
        if not _is_servable_ad_group(group):
            continue
        group_id = str(group.get("id"))
        active_ads = [ad for ad in ads_by_group.get(group_id, []) if _is_servable_yandex_ad(ad)]
        if active_ads:
            continue
        output.append(
            FindingDraft(
                entity_key=f"group:{group_id}",
                issue_location=f"group:{group_id}",
                campaign_external_id=str(group.get("campaign_id")),
                group_external_id=group_id,
                ad_external_id=None,
                evidence={
                    "campaign_id": group.get("campaign_id"),
                    "group_id": group_id,
                    "active_ads_count": 0,
                    "ads_count": len(ads_by_group.get(group_id, [])),
                },
                impact_ru="Активная группа не может откручивать трафик без активных объявлений.",
                recommendation_ru=rule.get("recommendation_ru", "Добавить или восстановить допущенные к показу объявления."),
            )
        )
    return output


def _active_group_without_targeting(ctx: L1Context, rule: dict[str, Any]) -> list[FindingDraft]:
    keywords_by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for keyword in ctx.keywords:
        keywords_by_group[str(keyword.get("ad_group_id"))].append(keyword)

    output: list[FindingDraft] = []
    for group in ctx.groups:
        if not _is_servable_ad_group(group):
            continue
        group_id = str(group.get("id"))
        active_keywords = [kw for kw in keywords_by_group.get(group_id, []) if _is_servable_yandex_keyword(kw)]
        if active_keywords:
            continue
        output.append(
            FindingDraft(
                entity_key=f"group:{group_id}",
                issue_location=f"group:{group_id}",
                campaign_external_id=str(group.get("campaign_id")),
                group_external_id=group_id,
                ad_external_id=None,
                evidence={
                    "campaign_id": group.get("campaign_id"),
                    "group_id": group_id,
                    "active_keywords_count": 0,
                },
                impact_ru="Группа активна, но не содержит рабочих таргетинговых сущностей.",
                recommendation_ru=rule.get(
                    "recommendation_ru",
                    "Добавить ключевые фразы, включить автотаргетинг или подключить аудитории.",
                ),
            )
        )
    return output


def _duplicate_keywords_in_group(ctx: L1Context, rule: dict[str, Any]) -> list[FindingDraft]:
    grouped: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    group_name_by_id = {str(group.get("id")): group.get("name") for group in ctx.groups}
    for keyword in ctx.keywords:
        group_id = str(keyword.get("ad_group_id"))
        norm = _normalize_keyword(str(keyword.get("phrase") or keyword.get("text") or ""))
        if norm:
            grouped[group_id][norm].append(keyword)

    output: list[FindingDraft] = []
    for group_id, normalized_map in grouped.items():
        for norm, kws in normalized_map.items():
            if len(kws) < 2:
                continue
            sample = kws[0]
            output.append(
                FindingDraft(
                    entity_key=f"group:{group_id}:keyword:{norm}",
                    issue_location=f"group:{group_id}",
                    campaign_external_id=str(sample.get("campaign_id")),
                    group_external_id=group_id,
                    ad_external_id=None,
                    evidence={
                        "campaign_id": sample.get("campaign_id"),
                        "group_id": group_id,
                        "group_name": group_name_by_id.get(group_id),
                        "keyword_ids": sorted(str(item.get("id")) for item in kws),
                        "keywords": sorted(str(item.get("phrase") or item.get("text") or "") for item in kws),
                        "normalized_keyword": norm,
                    },
                    impact_ru="Дубли ключевых фраз создают внутреннюю конкуренцию и размазывают статистику.",
                    recommendation_ru=rule.get("recommendation_ru", "Удалить дублирующиеся ключевые фразы."),
                )
            )
    return output


_PLACEHOLDER_RE = re.compile(r"(\{\{[^{}]+\}\}|\{[^{}]+\}|%[^%]+%|\[[^\[\]]+\]|<[^<>]+>)")
_DATE_RE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")
_YEAR_RE = re.compile(r"\b(20\d{2})\b")


def _unresolved_placeholder_in_text(ctx: L1Context, rule: dict[str, Any]) -> list[FindingDraft]:
    output: list[FindingDraft] = []
    for ad in ctx.ads:
        if not _is_servable_yandex_ad(ad):
            continue
        text_fields = [str(ad.get("title") or ""), str(ad.get("text") or "")]
        joined = " ".join(text_fields)
        matched = _PLACEHOLDER_RE.findall(joined)
        if not matched:
            continue
        output.append(
            FindingDraft(
                entity_key=f"ad:{ad.get('id')}:placeholder",
                issue_location=f"ad:{ad.get('id')}",
                campaign_external_id=str(ad.get("campaign_id")),
                group_external_id=str(ad.get("ad_group_id")),
                ad_external_id=str(ad.get("id")),
                evidence={
                    "campaign_id": ad.get("campaign_id"),
                    "group_id": ad.get("ad_group_id"),
                    "ad_id": ad.get("id"),
                    "matched_placeholder": matched,
                },
                impact_ru="Плейсхолдер в тексте объявления делает оффер некорректным и снижает доверие.",
                recommendation_ru=rule.get(
                    "recommendation_ru",
                    "Подставить фактическое значение вместо шаблона.",
                ),
            )
        )
    return output


def _duplicate_ads(ctx: L1Context, rule: dict[str, Any]) -> list[FindingDraft]:
    by_group: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for ad in ctx.ads:
        if not _is_servable_yandex_ad(ad):
            continue
        group_id = str(ad.get("ad_group_id"))
        signature = "|".join(
            [
                str(ad.get("title") or "").strip().lower(),
                str(ad.get("text") or "").strip().lower(),
                str(ad.get("url") or ad.get("final_url") or "").strip().lower(),
            ]
        )
        if signature == "||":
            continue
        by_group[group_id][signature].append(ad)
    out: list[FindingDraft] = []
    for group_id, grouped in by_group.items():
        for signature, ads in grouped.items():
            if len(ads) < 2:
                continue
            sample = ads[0]
            out.append(
                FindingDraft(
                    entity_key=f"group:{group_id}:duplicate_ad:{hashlib.sha256(signature.encode('utf-8')).hexdigest()[:16]}",
                    issue_location=f"group:{group_id}",
                    campaign_external_id=str(sample.get("campaign_id")),
                    group_external_id=group_id,
                    ad_external_id=None,
                    evidence={
                        "campaign_id": sample.get("campaign_id"),
                        "group_id": group_id,
                        "ad_ids": sorted(str(item.get("id")) for item in ads),
                    },
                    impact_ru="В группе есть дубли объявлений, это снижает управляемость и искажает статистику.",
                    recommendation_ru=rule.get("recommendation_ru", "Оставить одно объявление, остальные удалить или переписать."),
                )
            )
    return out


def _duplicate_sitelinks(ctx: L1Context, rule: dict[str, Any]) -> list[FindingDraft]:
    out: list[FindingDraft] = []
    for ad in ctx.ads:
        if not _is_servable_yandex_ad(ad):
            continue
        sitelinks = ad.get("sitelinks")
        if not isinstance(sitelinks, list) or len(sitelinks) < 2:
            continue
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in sitelinks:
            if not isinstance(item, dict):
                continue
            signature = "|".join(
                [
                    str(item.get("title") or "").strip().lower(),
                    str(item.get("description") or "").strip().lower(),
                    str(item.get("url") or "").strip().lower(),
                ]
            )
            grouped[signature].append(item)
        duplicates = [rows for rows in grouped.values() if len(rows) > 1]
        if not duplicates:
            continue
        out.append(
            FindingDraft(
                entity_key=f"ad:{ad.get('id')}:duplicate_sitelinks",
                issue_location=f"ad:{ad.get('id')}",
                campaign_external_id=str(ad.get("campaign_id")),
                group_external_id=str(ad.get("ad_group_id")),
                ad_external_id=str(ad.get("id")),
                evidence={
                    "campaign_id": ad.get("campaign_id"),
                    "group_id": ad.get("ad_group_id"),
                    "ad_id": ad.get("id"),
                    "duplicate_sitelinks": duplicates,
                },
                impact_ru="Дубли быстрых ссылок ухудшают качество объявления и занимают место полезных ссылок.",
                recommendation_ru=rule.get("recommendation_ru", "Оставить только уникальные быстрые ссылки."),
            )
        )
    return out


def _keyword_conflicts_with_group_negatives(ctx: L1Context, rule: dict[str, Any]) -> list[FindingDraft]:
    groups = {str(g.get("id")): g for g in ctx.groups}
    out: list[FindingDraft] = []
    for keyword in ctx.keywords:
        if not _is_servable_yandex_keyword(keyword):
            continue
        group_id = str(keyword.get("ad_group_id"))
        group = groups.get(group_id)
        if not group:
            continue
        negatives = _negative_tokens(group.get("negative_keywords"))
        if not negatives:
            continue
        phrase = str(keyword.get("phrase") or keyword.get("text") or "")
        conflicts = sorted(_keyword_positive_tokens(phrase) & negatives)
        if not conflicts:
            continue
        out.append(
            FindingDraft(
                entity_key=f"keyword:{keyword.get('id')}:group_negative_conflict",
                issue_location=f"group:{group_id}",
                campaign_external_id=str(keyword.get("campaign_id")),
                group_external_id=group_id,
                ad_external_id=None,
                evidence={
                    "campaign_id": keyword.get("campaign_id"),
                    "group_id": group_id,
                    "keyword_id": keyword.get("id"),
                    "keyword_text": phrase,
                    "conflict_tokens": conflicts,
                },
                impact_ru="Ключевая фраза конфликтует с минус-словами группы и теряет показы.",
                recommendation_ru=rule.get("recommendation_ru", "Согласовать ключ и минус-слова в группе."),
            )
        )
    return out


def _keyword_conflicts_with_campaign_negatives(ctx: L1Context, rule: dict[str, Any]) -> list[FindingDraft]:
    campaigns = {str(c.get("id")): c for c in ctx.campaigns}
    out: list[FindingDraft] = []
    for keyword in ctx.keywords:
        if not _is_servable_yandex_keyword(keyword):
            continue
        campaign_id = str(keyword.get("campaign_id"))
        campaign = campaigns.get(campaign_id)
        if not campaign:
            continue
        negatives = _negative_tokens(campaign.get("negative_keywords"))
        if not negatives:
            continue
        phrase = str(keyword.get("phrase") or keyword.get("text") or "")
        conflicts = sorted(_keyword_positive_tokens(phrase) & negatives)
        if not conflicts:
            continue
        out.append(
            FindingDraft(
                entity_key=f"keyword:{keyword.get('id')}:campaign_negative_conflict",
                issue_location=f"campaign:{campaign_id}",
                campaign_external_id=campaign_id,
                group_external_id=str(keyword.get("ad_group_id")),
                ad_external_id=None,
                evidence={
                    "campaign_id": campaign_id,
                    "group_id": keyword.get("ad_group_id"),
                    "keyword_id": keyword.get("id"),
                    "keyword_text": phrase,
                    "conflict_tokens": conflicts,
                },
                impact_ru="Ключевая фраза конфликтует с минус-словами кампании и не получает целевой трафик.",
                recommendation_ru=rule.get("recommendation_ru", "Проверить кросс-минусовку на уровне кампании."),
            )
        )
    return out


def _missing_required_extensions(ctx: L1Context, rule: dict[str, Any]) -> list[FindingDraft]:
    required = [str(x) for x in (rule.get("required_extensions") or []) if str(x)]
    if not required:
        required = ["sitelinks", "callouts", "display_url", "contact_info", "image"]
    out: list[FindingDraft] = []
    for ad in ctx.ads:
        if not _is_servable_yandex_ad(ad):
            continue
        missing: list[str] = []
        for key in required:
            value = ad.get(key)
            if isinstance(value, list) and len(value) == 0:
                missing.append(key)
            elif value in (None, "", {}):
                missing.append(key)
        if not missing:
            continue
        out.append(
            FindingDraft(
                entity_key=f"ad:{ad.get('id')}:missing_extensions",
                issue_location=f"ad:{ad.get('id')}",
                campaign_external_id=str(ad.get("campaign_id")),
                group_external_id=str(ad.get("ad_group_id")),
                ad_external_id=str(ad.get("id")),
                evidence={"ad_id": ad.get("id"), "missing_extensions": missing},
                impact_ru="У объявления не хватает обязательных расширений, снижается кликабельность и полнота оффера.",
                recommendation_ru=rule.get("recommendation_ru", "Добавить обязательные расширения объявления."),
            )
        )
    return out


def _active_ad_rejected_or_restricted(ctx: L1Context, rule: dict[str, Any]) -> list[FindingDraft]:
    out: list[FindingDraft] = []
    for ad in ctx.ads:
        if not _is_servable_yandex_ad(ad):
            continue
        moderation = str(ad.get("moderation_status") or "").lower()
        serving = str(ad.get("serving_status") or "").lower()
        if moderation not in {"rejected", "limited"} and serving not in {"not_eligible", "suspended"}:
            continue
        out.append(
            FindingDraft(
                entity_key=f"ad:{ad.get('id')}:moderation_problem",
                issue_location=f"ad:{ad.get('id')}",
                campaign_external_id=str(ad.get("campaign_id")),
                group_external_id=str(ad.get("ad_group_id")),
                ad_external_id=str(ad.get("id")),
                evidence={
                    "ad_id": ad.get("id"),
                    "moderation_status": ad.get("moderation_status"),
                    "serving_status": ad.get("serving_status"),
                },
                impact_ru="Активное объявление отклонено или ограничено и не участвует полноценно в показах.",
                recommendation_ru=rule.get("recommendation_ru", "Исправить замечания модерации и восстановить показы."),
            )
        )
    return out


def _group_all_ads_rejected(ctx: L1Context, rule: dict[str, Any]) -> list[FindingDraft]:
    by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ad in ctx.ads:
        by_group[str(ad.get("ad_group_id"))].append(ad)
    out: list[FindingDraft] = []
    for group in ctx.groups:
        if not _is_servable_ad_group(group):
            continue
        group_id = str(group.get("id"))
        ads = [a for a in by_group.get(group_id, []) if _is_servable_yandex_ad(a)]
        if not ads:
            continue
        all_rejected = True
        for ad in ads:
            moderation = str(ad.get("moderation_status") or "").lower()
            serving = str(ad.get("serving_status") or "").lower()
            if moderation not in {"rejected", "limited"} and serving not in {"not_eligible", "suspended"}:
                all_rejected = False
                break
        if not all_rejected:
            continue
        out.append(
            FindingDraft(
                entity_key=f"group:{group_id}:all_ads_rejected",
                issue_location=f"group:{group_id}",
                campaign_external_id=str(group.get("campaign_id")),
                group_external_id=group_id,
                ad_external_id=None,
                evidence={
                    "campaign_id": group.get("campaign_id"),
                    "group_id": group_id,
                    "ad_ids": sorted(str(a.get("id")) for a in ads),
                },
                impact_ru="Все активные объявления в группе отклонены/ограничены, группа не может эффективно откручиваться.",
                recommendation_ru=rule.get("recommendation_ru", "Исправить объявления группы и пройти модерацию."),
            )
        )
    return out


def _expired_date_in_ad_text(ctx: L1Context, rule: dict[str, Any]) -> list[FindingDraft]:
    now = datetime.now(timezone.utc).date()
    out: list[FindingDraft] = []
    for ad in ctx.ads:
        if not _is_servable_yandex_ad(ad):
            continue
        text = f"{ad.get('title') or ''} {ad.get('text') or ''}"
        for match in _DATE_RE.finditer(text):
            day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
            try:
                value = datetime(year=year, month=month, day=day, tzinfo=timezone.utc).date()
            except ValueError:
                continue
            if value >= now:
                continue
            out.append(
                FindingDraft(
                    entity_key=f"ad:{ad.get('id')}:expired_date:{match.group(0)}",
                    issue_location=f"ad:{ad.get('id')}",
                    campaign_external_id=str(ad.get("campaign_id")),
                    group_external_id=str(ad.get("ad_group_id")),
                    ad_external_id=str(ad.get("id")),
                    evidence={"ad_id": ad.get("id"), "expired_date": match.group(0)},
                    impact_ru="В тексте объявления указана прошедшая дата, оффер выглядит неактуальным.",
                    recommendation_ru=rule.get("recommendation_ru", "Обновить дату в тексте объявления."),
                )
            )
    return out


def _expired_date_in_extensions(ctx: L1Context, rule: dict[str, Any]) -> list[FindingDraft]:
    now = datetime.now(timezone.utc).date()
    out: list[FindingDraft] = []
    for ext in ctx.extensions:
        ad_id = ext.get("ad_id")
        campaign_id = str(ext.get("campaign_id") or "")
        group_id = str(ext.get("ad_group_id") or "")
        sitelinks = ext.get("sitelinks") or []
        if not isinstance(sitelinks, list):
            continue
        for idx, sl in enumerate(sitelinks):
            if not isinstance(sl, dict):
                continue
            text = f"{sl.get('title') or ''} {sl.get('description') or ''}"
            for match in _DATE_RE.finditer(text):
                day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
                try:
                    value = datetime(year=year, month=month, day=day, tzinfo=timezone.utc).date()
                except ValueError:
                    continue
                if value >= now:
                    continue
                out.append(
                    FindingDraft(
                        entity_key=f"ext:{ad_id}:sitelink[{idx}]:expired:{match.group(0)}",
                        issue_location=f"ad:{ad_id}" if ad_id else f"campaign:{campaign_id}",
                        campaign_external_id=campaign_id or None,
                        group_external_id=group_id or None,
                        ad_external_id=str(ad_id) if ad_id is not None else None,
                        evidence={
                            "ad_id": ad_id,
                            "sitelink_index": idx,
                            "sitelink_title": sl.get("title"),
                            "expired_date": match.group(0),
                        },
                        impact_ru="В тексте расширения (быстрой ссылки) указана прошедшая дата.",
                        recommendation_ru=rule.get("recommendation_ru", "Обновить даты в расширениях объявления."),
                    )
                )
    return out


def _past_year_in_text(ctx: L1Context, rule: dict[str, Any]) -> list[FindingDraft]:
    current_year = datetime.now(timezone.utc).year
    out: list[FindingDraft] = []
    for ad in ctx.ads:
        if not _is_servable_yandex_ad(ad):
            continue
        text = f"{ad.get('title') or ''} {ad.get('text') or ''}"
        years = sorted({int(m.group(1)) for m in _YEAR_RE.finditer(text)})
        stale = [year for year in years if year < current_year]
        if not stale:
            continue
        out.append(
            FindingDraft(
                entity_key=f"ad:{ad.get('id')}:past_year",
                issue_location=f"ad:{ad.get('id')}",
                campaign_external_id=str(ad.get("campaign_id")),
                group_external_id=str(ad.get("ad_group_id")),
                ad_external_id=str(ad.get("id")),
                evidence={"ad_id": ad.get("id"), "mentioned_years": stale, "current_year": current_year},
                impact_ru="В тексте объявления упоминается прошлый год, это снижает актуальность оффера.",
                recommendation_ru=rule.get("recommendation_ru", "Актуализировать год в текстах объявлений."),
            )
        )
    return out


def _duplicate_keywords_with_overlap(ctx: L1Context, rule: dict[str, Any]) -> list[FindingDraft]:
    by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for kw in ctx.keywords:
        if _is_servable_yandex_keyword(kw):
            by_group[str(kw.get("ad_group_id"))].append(kw)
    out: list[FindingDraft] = []
    for group_id, kws in by_group.items():
        for i in range(len(kws)):
            left = kws[i]
            left_tokens = _keyword_positive_tokens(str(left.get("phrase") or left.get("text") or ""))
            if not left_tokens:
                continue
            for j in range(i + 1, len(kws)):
                right = kws[j]
                right_tokens = _keyword_positive_tokens(str(right.get("phrase") or right.get("text") or ""))
                if not right_tokens or left_tokens == right_tokens:
                    continue
                inter = left_tokens & right_tokens
                if not inter:
                    continue
                overlap_ratio = len(inter) / max(1, min(len(left_tokens), len(right_tokens)))
                if overlap_ratio < 0.7:
                    continue
                sample = left
                out.append(
                    FindingDraft(
                        entity_key=f"group:{group_id}:overlap_kw:{left.get('id')}:{right.get('id')}",
                        issue_location=f"group:{group_id}",
                        campaign_external_id=str(sample.get("campaign_id")),
                        group_external_id=group_id,
                        ad_external_id=None,
                        evidence={
                            "campaign_id": sample.get("campaign_id"),
                            "group_id": group_id,
                            "left_keyword_id": left.get("id"),
                            "right_keyword_id": right.get("id"),
                            "left_keyword": left.get("phrase") or left.get("text"),
                            "right_keyword": right.get("phrase") or right.get("text"),
                            "intersection_tokens": sorted(inter),
                            "overlap_ratio": overlap_ratio,
                        },
                        impact_ru="Похожие ключевые фразы частично дублируют спрос и создают внутреннюю конкуренцию.",
                        recommendation_ru=rule.get("recommendation_ru", "Развести семантику или объединить дублирующие ключи."),
                    )
                )
    return out


def _group_keyword_overlap(ctx: L1Context, rule: dict[str, Any]) -> list[FindingDraft]:
    group_meta = {str(g.get("id")): g for g in ctx.groups}
    by_campaign_group: dict[str, dict[str, set[str]]] = defaultdict(dict)
    for kw in ctx.keywords:
        if not _is_servable_yandex_keyword(kw):
            continue
        campaign_id = str(kw.get("campaign_id"))
        group_id = str(kw.get("ad_group_id"))
        phrase = str(kw.get("phrase") or kw.get("text") or "")
        normalized = _normalize_keyword(phrase)
        if not normalized:
            continue
        by_campaign_group.setdefault(campaign_id, {}).setdefault(group_id, set()).add(normalized)
    out: list[FindingDraft] = []
    for campaign_id, groups in by_campaign_group.items():
        group_ids = sorted(groups.keys())
        for i in range(len(group_ids)):
            left_id = group_ids[i]
            for j in range(i + 1, len(group_ids)):
                right_id = group_ids[j]
                common = sorted(groups[left_id] & groups[right_id])
                if not common:
                    continue
                out.append(
                    FindingDraft(
                        entity_key=f"campaign:{campaign_id}:group_overlap:{left_id}:{right_id}",
                        issue_location=f"campaign:{campaign_id}",
                        campaign_external_id=campaign_id,
                        group_external_id=None,
                        ad_external_id=None,
                        evidence={
                            "campaign_id": campaign_id,
                            "left_group_id": left_id,
                            "left_group_name": group_meta.get(left_id, {}).get("name"),
                            "right_group_id": right_id,
                            "right_group_name": group_meta.get(right_id, {}).get("name"),
                            "overlap_keywords": common,
                        },
                        impact_ru="Одинаковые ключи в разных группах одной кампании ведут к само-конкуренции.",
                        recommendation_ru=rule.get("recommendation_ru", "Развести ключи между группами или добавить минус-слова."),
                    )
                )
    return out


def _missing_cross_negatives(ctx: L1Context, rule: dict[str, Any]) -> list[FindingDraft]:
    groups = [g for g in ctx.groups if _is_servable_ad_group(g)]
    keywords_by_group: dict[str, set[str]] = defaultdict(set)
    for kw in ctx.keywords:
        if not _is_servable_yandex_keyword(kw):
            continue
        group_id = str(kw.get("ad_group_id"))
        keywords_by_group[group_id] |= _keyword_positive_tokens(str(kw.get("phrase") or kw.get("text") or ""))
    out: list[FindingDraft] = []
    by_campaign: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for g in groups:
        by_campaign[str(g.get("campaign_id"))].append(g)
    for campaign_id, campaign_groups in by_campaign.items():
        for g in campaign_groups:
            g_id = str(g.get("id"))
            g_tokens = keywords_by_group.get(g_id, set())
            if not g_tokens:
                continue
            g_negatives = _negative_tokens(g.get("negative_keywords"))
            missing: set[str] = set()
            for other in campaign_groups:
                other_id = str(other.get("id"))
                if other_id == g_id:
                    continue
                other_tokens = keywords_by_group.get(other_id, set())
                if not other_tokens:
                    continue
                # If one group is narrower, broader group should exclude narrower tail.
                if other_tokens < g_tokens:
                    missing |= other_tokens - g_negatives
            if not missing:
                continue
            out.append(
                FindingDraft(
                    entity_key=f"group:{g_id}:missing_cross_negatives",
                    issue_location=f"group:{g_id}",
                    campaign_external_id=campaign_id,
                    group_external_id=g_id,
                    ad_external_id=None,
                    evidence={
                        "campaign_id": campaign_id,
                        "group_id": g_id,
                        "missing_negative_tokens": sorted(missing),
                    },
                    impact_ru="Отсутствует кросс-минусовка между группами, трафик пересекается и дорожает.",
                    recommendation_ru=rule.get("recommendation_ru", "Добавить кросс-минус-слова между группами."),
                )
            )
    return out


def _campaign_self_competition_by_geo_and_semantics(ctx: L1Context, rule: dict[str, Any]) -> list[FindingDraft]:
    campaign_keywords: dict[str, set[str]] = defaultdict(set)
    for kw in ctx.keywords:
        if not _is_servable_yandex_keyword(kw):
            continue
        campaign_id = str(kw.get("campaign_id"))
        campaign_keywords[campaign_id].add(_normalize_keyword(str(kw.get("phrase") or kw.get("text") or "")))
    campaigns = [c for c in ctx.campaigns if _is_active_yandex_campaign(c)]
    out: list[FindingDraft] = []
    for i in range(len(campaigns)):
        left = campaigns[i]
        left_id = str(left.get("id"))
        left_geo = {str(x).strip().lower() for x in (left.get("geo") or [])}
        left_kw = {x for x in campaign_keywords.get(left_id, set()) if x}
        if not left_geo or not left_kw:
            continue
        for j in range(i + 1, len(campaigns)):
            right = campaigns[j]
            right_id = str(right.get("id"))
            right_geo = {str(x).strip().lower() for x in (right.get("geo") or [])}
            right_kw = {x for x in campaign_keywords.get(right_id, set()) if x}
            geo_overlap = left_geo & right_geo
            kw_overlap = left_kw & right_kw
            if not geo_overlap or not kw_overlap:
                continue
            out.append(
                FindingDraft(
                    entity_key=f"campaign_overlap:{left_id}:{right_id}",
                    issue_location=f"account:{ctx.account_id}",
                    campaign_external_id=left_id,
                    group_external_id=None,
                    ad_external_id=None,
                    evidence={
                        "left_campaign_id": left_id,
                        "right_campaign_id": right_id,
                        "geo_overlap": sorted(geo_overlap),
                        "semantic_overlap_count": len(kw_overlap),
                        "semantic_overlap_examples": sorted(list(kw_overlap))[:10],
                    },
                    impact_ru="Кампании пересекаются по гео и семантике, возникает само-конкуренция внутри аккаунта.",
                    recommendation_ru=rule.get("recommendation_ru", "Развести гео/семантику между кампаниями."),
                )
            )
    return out


def _geo_text_targeting_mismatch(ctx: L1Context, rule: dict[str, Any]) -> list[FindingDraft]:
    # Minimal deterministic detector for current test fixture.
    city_aliases = {
        "москва": {"москва", "москов"},
        "санкт-петербург": {"санкт-петербург", "санкт петербург", "спб", "питер"},
    }
    campaigns = {str(c.get("id")): c for c in ctx.campaigns}
    out: list[FindingDraft] = []
    for ad in ctx.ads:
        if not _is_servable_yandex_ad(ad):
            continue
        campaign_id = str(ad.get("campaign_id"))
        campaign = campaigns.get(campaign_id)
        if not campaign:
            continue
        campaign_geo_text = " ".join(str(x).lower() for x in (campaign.get("geo") or []))
        ad_text = f"{str(ad.get('title') or '').lower()} {str(ad.get('text') or '').lower()}"
        for canonical, aliases in city_aliases.items():
            mentions_city = any(alias in ad_text for alias in aliases)
            campaign_has_city = any(alias in campaign_geo_text for alias in aliases)
            if mentions_city and not campaign_has_city:
                out.append(
                    FindingDraft(
                        entity_key=f"ad:{ad.get('id')}:geo_mismatch:{canonical}",
                        issue_location=f"ad:{ad.get('id')}",
                        campaign_external_id=campaign_id,
                        group_external_id=str(ad.get("ad_group_id")),
                        ad_external_id=str(ad.get("id")),
                        evidence={
                            "campaign_id": campaign_id,
                            "ad_id": ad.get("id"),
                            "mentioned_city": canonical,
                            "campaign_geo": campaign.get("geo") or [],
                        },
                        impact_ru="В тексте объявления указан город, который не соответствует геотаргетингу кампании.",
                        recommendation_ru=rule.get("recommendation_ru", "Согласовать гео в тексте объявления и таргетинге."),
                    )
                )
                break
    return out


def build_l1_rule_registry() -> dict[str, RuleHandler]:
    return {
        "ACTIVE_CAMPAIGN_WITHOUT_ACTIVE_GROUPS": _active_campaign_without_active_groups,
        "ACTIVE_GROUP_WITHOUT_ACTIVE_ADS": _active_group_without_active_ads,
        "ACTIVE_GROUP_WITHOUT_TARGETING": _active_group_without_targeting,
        "GROUP_ALL_ADS_REJECTED": _group_all_ads_rejected,
        "ACTIVE_AD_REJECTED_OR_RESTRICTED": _active_ad_rejected_or_restricted,
        "DUPLICATE_KEYWORDS_IN_GROUP": _duplicate_keywords_in_group,
        "DUPLICATE_KEYWORDS_WITH_OVERLAP": _duplicate_keywords_with_overlap,
        "GROUP_KEYWORD_OVERLAP": _group_keyword_overlap,
        "MISSING_CROSS_NEGATIVES": _missing_cross_negatives,
        "CAMPAIGN_SELF_COMPETITION_BY_GEO_AND_SEMANTICS": _campaign_self_competition_by_geo_and_semantics,
        "CAMPAIGN_GEO_OVERLAPS_CAMPAIGN_NEGATIVES": _campaign_geo_overlaps_campaign_negatives,
        "GEO_TEXT_TARGETING_MISMATCH": _geo_text_targeting_mismatch,
        "KEYWORD_CONFLICTS_WITH_GROUP_NEGATIVES": _keyword_conflicts_with_group_negatives,
        "KEYWORD_CONFLICTS_WITH_CAMPAIGN_NEGATIVES": _keyword_conflicts_with_campaign_negatives,
        "DUPLICATE_ADS": _duplicate_ads,
        "DUPLICATE_SITELINKS": _duplicate_sitelinks,
        "MISSING_REQUIRED_EXTENSIONS": _missing_required_extensions,
        "EXPIRED_DATE_IN_AD_TEXT": _expired_date_in_ad_text,
        "EXPIRED_DATE_IN_EXTENSIONS": _expired_date_in_extensions,
        "PAST_YEAR_IN_TEXT": _past_year_in_text,
        "UNRESOLVED_PLACEHOLDER_IN_TEXT": _unresolved_placeholder_in_text,
    }
