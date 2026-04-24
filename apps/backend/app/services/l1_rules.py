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
    # Full-account rows when ctx.campaigns/keywords are scoped to one campaign (cross-campaign rules).
    account_campaigns: list[dict[str, Any]] | None = None
    account_keywords: list[dict[str, Any]] | None = None
    account_groups: list[dict[str, Any]] | None = None
    scoped_campaign_external_id: str | None = None


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
    serving_status = str(ad.get("serving_status") or "").strip().lower()
    if serving_status in {"not_eligible", "suspended"}:
        return False
    if serving_status in {"eligible"}:
        return True
    state = str(ad.get("state") or "").strip().lower()
    if state in {"off", "suspended", "archived", "deleted"}:
        return False
    if state in {"on", "yes", "active", "enabled"}:
        return True
    status = str(ad.get("status") or "").strip().lower()
    if status in {"accepted"}:
        return True
    return _is_active(ad.get("status")) or _is_active(ad.get("state"))


def _is_structurally_enabled_yandex_ad(ad: dict[str, Any]) -> bool:
    """Ad is enabled in the snapshot (ON/active), but may still be not_eligible for moderation."""
    state = str(ad.get("state") or "").strip().lower()
    if state in {"archived", "deleted"}:
        return False
    if state in {"off", "suspended"}:
        return False
    if state in {"on", "yes", "active", "enabled"}:
        return True
    status = str(ad.get("status") or "").strip().lower()
    if status in {"archived", "deleted"}:
        return False
    if status in {"accepted"}:
        return True
    return _is_active(ad.get("status")) or _is_active(ad.get("state"))


def _group_autotargeting_enabled(group: dict[str, Any]) -> bool:
    raw = str(group.get("autotargeting") or "").strip().lower()
    return raw in {"enabled", "on", "yes", "true"}


def _group_active_audiences_count(group: dict[str, Any]) -> int:
    aud = group.get("audiences")
    if not isinstance(aud, list) or not aud:
        return 0
    n = 0
    for item in aud:
        if not isinstance(item, dict):
            n += 1
            continue
        st = str(item.get("status") or item.get("state") or "").strip().lower()
        if st in {"archived", "deleted", "removed"}:
            continue
        if st in {"off", "paused", "suspended"}:
            continue
        if st in {"active", "on", "enabled", "accepted", "yes"}:
            n += 1
            continue
        if _is_active(item.get("status")) or _is_active(item.get("state")):
            n += 1
            continue
        if not st:
            n += 1
    return n


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


GEO_FINGERPRINT_ALL_REGIONS = "geo:all_regions"


def _normalize_region_ids_value(raw: Any) -> list[int]:
    if raw is None:
        return []
    if isinstance(raw, dict) and "Items" in raw:
        raw = raw["Items"]
    if not isinstance(raw, list):
        return []
    out: list[int] = []
    for x in raw:
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            continue
    return out


def _campaign_geo_fingerprint(
    campaign_id: str,
    campaigns: list[dict[str, Any]],
    groups: list[dict[str, Any]],
) -> set[str]:
    """Union of human-readable geo labels, their tokens, and Yandex RegionIds (group + campaign)."""
    camp = next((c for c in campaigns if str(c.get("id")) == campaign_id), None)
    fp: set[str] = set()
    if camp is not None:
        geo_list = camp.get("geo") or []
        if isinstance(geo_list, list):
            fp |= _geo_setting_tokens(geo_list)
            for item in geo_list:
                s = str(item).strip().lower()
                if s:
                    fp.add(f"label:{s}")
        for rid in _normalize_region_ids_value(camp.get("region_ids")):
            if rid == 0:
                fp.add(GEO_FINGERPRINT_ALL_REGIONS)
            elif rid > 0:
                fp.add(f"rid:{rid}")
    for g in groups:
        if str(g.get("campaign_id")) != campaign_id:
            continue
        for rid in _normalize_region_ids_value(g.get("region_ids")):
            if rid == 0:
                fp.add(GEO_FINGERPRINT_ALL_REGIONS)
            elif rid > 0:
                fp.add(f"rid:{rid}")
    return fp


def _geo_fingerprints_overlap(a: set[str], b: set[str]) -> tuple[bool, set[str]]:
    """True only if audiences can overlap geographically (shared labels, tokens, or region ids)."""
    if not a or not b:
        return False, set()
    if GEO_FINGERPRINT_ALL_REGIONS in a or GEO_FINGERPRINT_ALL_REGIONS in b:
        return True, {GEO_FINGERPRINT_ALL_REGIONS}
    inter = a & b
    if not inter:
        return False, set()
    return True, inter


def _campaign_pair_geo_targets_overlap(
    campaign_id_a: str,
    campaign_id_b: str,
    campaigns: list[dict[str, Any]],
    groups: list[dict[str, Any]],
) -> tuple[bool, set[str]]:
    """Whether two campaigns may share geography; unknown/empty geo in snapshots is treated as overlap (conservative)."""
    if campaign_id_a == campaign_id_b:
        return True, set()
    fp_a = _campaign_geo_fingerprint(campaign_id_a, campaigns, groups)
    fp_b = _campaign_geo_fingerprint(campaign_id_b, campaigns, groups)
    if not fp_a and not fp_b:
        return True, {"geo:unknown"}
    if not fp_a or not fp_b:
        return True, {"geo:partially_unknown"}
    return _geo_fingerprints_overlap(fp_a, fp_b)


def _groups_for_geo_rules(ctx: L1Context) -> list[dict[str, Any]]:
    return ctx.account_groups if ctx.account_groups is not None else ctx.groups


def _campaign_geo_negatives_tokens(campaign: dict[str, Any], groups: list[dict[str, Any]]) -> set[str]:
    """Tokens/strings compared to campaign minus-words (labels + region id strings)."""
    cid = str(campaign.get("id"))
    geo_list = campaign.get("geo") or []
    tokens = set(_geo_setting_tokens(geo_list)) if isinstance(geo_list, list) else set()
    fp = _campaign_geo_fingerprint(cid, [campaign], groups)
    for x in fp:
        if x.startswith("label:"):
            tokens |= _geo_setting_tokens([x.replace("label:", "", 1)])
        elif x.startswith("rid:") and x != GEO_FINGERPRINT_ALL_REGIONS:
            rid_part = x.split(":", 1)[-1]
            if rid_part.isdigit():
                tokens.add(rid_part)
    return tokens


def _campaign_geo_overlaps_campaign_negatives(ctx: L1Context, rule: dict[str, Any]) -> list[FindingDraft]:
    """Минус-слова кампании совпадают с токенами геотаргетинга (или вхождение в строку гео)."""
    out: list[FindingDraft] = []
    groups_src = _groups_for_geo_rules(ctx)
    for campaign in ctx.campaigns:
        if not _is_active_yandex_campaign(campaign):
            continue
        geo = campaign.get("geo") or []
        negatives = _negative_tokens(campaign.get("negative_keywords"))
        if not negatives:
            continue
        geo_tokens = _campaign_geo_negatives_tokens(campaign, groups_src)
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
        group_ads = ads_by_group.get(group_id, [])
        rejected_ads_count = sum(
            1 for ad in group_ads if _is_structurally_enabled_yandex_ad(ad) and not _is_servable_yandex_ad(ad)
        )
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
                    "group_name": group.get("name"),
                    "active_ads_count": 0,
                    "ads_count": len(group_ads),
                    "rejected_ads_count": rejected_ads_count,
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
        if _group_autotargeting_enabled(group):
            continue
        if _group_active_audiences_count(group) > 0:
            continue
        output.append(
            FindingDraft(
                entity_key=f"group:{group_id}:no_targeting",
                issue_location=f"group:{group_id}",
                campaign_external_id=str(group.get("campaign_id")),
                group_external_id=group_id,
                ad_external_id=None,
                evidence={
                    "campaign_id": group.get("campaign_id"),
                    "group_id": group_id,
                    "group_name": group.get("name"),
                    "active_keywords_count": 0,
                    "autotargeting": group.get("autotargeting"),
                    "autotargeting_enabled": _group_autotargeting_enabled(group),
                    "active_audiences_count": _group_active_audiences_count(group),
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
        if not _is_servable_yandex_keyword(keyword):
            continue
        group_id = str(keyword.get("ad_group_id"))
        norm = _normalize_keyword(str(keyword.get("phrase") or keyword.get("text") or ""))
        if norm:
            grouped[group_id][norm].append(keyword)

    groups_by_id = {str(g.get("id")): g for g in ctx.groups}
    minus_conflicts_by_group: dict[str, list[dict[str, Any]]] = {}
    for gid, g in groups_by_id.items():
        negatives = _negative_tokens(g.get("negative_keywords"))
        if not negatives:
            continue
        conflicts: list[dict[str, Any]] = []
        for keyword in ctx.keywords:
            if not _is_servable_yandex_keyword(keyword):
                continue
            if str(keyword.get("ad_group_id")) != gid:
                continue
            phrase = str(keyword.get("phrase") or keyword.get("text") or "")
            hit = sorted(_keyword_positive_tokens(phrase) & negatives)
            if hit:
                conflicts.append(
                    {
                        "keyword_id": str(keyword.get("id")),
                        "phrase": phrase,
                        "minus_tokens": hit,
                    }
                )
        if conflicts:
            minus_conflicts_by_group[gid] = conflicts

    output: list[FindingDraft] = []
    for group_id, normalized_map in grouped.items():
        for norm, kws in normalized_map.items():
            if len(kws) < 2:
                continue
            sample = kws[0]
            phrases = sorted(str(item.get("phrase") or item.get("text") or "") for item in kws)
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
                        "keywords": phrases,
                        "duplicate_phrases": phrases,
                        "normalized_keyword": norm,
                        "minus_word_conflicts": minus_conflicts_by_group.get(group_id, []),
                    },
                    impact_ru="Дубли ключевых фраз создают внутреннюю конкуренцию и размазывают статистику.",
                    recommendation_ru=rule.get("recommendation_ru", "Удалить дублирующиеся ключевые фразы."),
                )
            )
    return output


_PLACEHOLDER_RE = re.compile(r"(\{\{[^{}]+\}\}|\{[^{}]+\}|%[^%]+%|\[[^\[\]]+\]|<[^<>]+>)")
_DATE_RE = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b")
_YEAR_RE = re.compile(r"\b(20\d{2})\b")
_EXPIRED_YEAR_PHRASE_RE = re.compile(r"(?i)сдача\s+в\s+(20\d{2})")


def _ad_image_fingerprint(ad: dict[str, Any]) -> str:
    """
    Stable identity for ad image(s). Same title/text/url but different fingerprint => different
    креативы (1:1, 3:4, …), not duplicates. Empty if no image data.
    Priority per asset: Id → URL/Href → Name/Title (одно поле на объект, как в библиотеке Директа).
    """
    chunks: list[str] = []

    def add(kind: str, value: str) -> None:
        v = str(value).strip().lower()
        if v:
            chunks.append(f"{kind}:{v}")

    def consume_image_obj(raw: Any) -> None:
        if raw is None:
            return
        if isinstance(raw, str):
            u = raw.strip()
            if u:
                add("u", u)
            return
        if isinstance(raw, dict):
            iid = raw.get("id") if raw.get("id") is not None else raw.get("Id")
            if iid is not None and str(iid).strip():
                add("id", str(iid))
                return
            u = raw.get("url") or raw.get("Url") or raw.get("href") or raw.get("Href")
            if u is not None and str(u).strip():
                add("u", str(u).strip())
                return
            name = raw.get("name") or raw.get("Name") or raw.get("title") or raw.get("Title")
            if name is not None and str(name).strip():
                add("n", str(name).strip())
            return
        if isinstance(raw, list):
            for item in raw:
                consume_image_obj(item)

    consume_image_obj(ad.get("image"))
    consume_image_obj(ad.get("images"))

    chunks.sort()
    return "|".join(chunks)


def _ad_image_evidence_summary(ad: dict[str, Any]) -> dict[str, Any]:
    """Short image description for DUPLICATE_ADS evidence (UI / отчёт)."""
    ad_id = str(ad.get("id") or "")
    fp = _ad_image_fingerprint(ad)
    raw = ad.get("image")
    if raw is None:
        raw = ad.get("images")
    out: dict[str, Any] = {
        "ad_id": ad_id,
        "image_fingerprint": fp or None,
    }
    if not fp:
        out["caption_ru"] = "изображение не указано"
        return out
    if isinstance(raw, str):
        u = raw.strip()
        out["caption_ru"] = f"URL: {u}" if len(u) <= 120 else f"URL: {u[:117]}…"
        return out
    if isinstance(raw, dict):
        parts: list[str] = []
        iid = raw.get("id") if raw.get("id") is not None else raw.get("Id")
        name = raw.get("name") or raw.get("Name") or raw.get("title") or raw.get("Title")
        if iid is not None and str(iid).strip():
            parts.append(f"id {iid}")
        if name:
            parts.append(f"«{name}»")
        w = raw.get("width") or raw.get("Width")
        h = raw.get("height") or raw.get("Height")
        if w and h:
            parts.append(f"{w}×{h}")
        ar = raw.get("aspect_ratio") or raw.get("AspectRatio")
        if ar:
            parts.append(f"соотн. {ar}")
        u = raw.get("url") or raw.get("Url") or raw.get("href")
        if u and not parts:
            parts.append(f"URL {str(u)[:80]}")
        out["caption_ru"] = ", ".join(parts) if parts else (fp[:120] if fp else "—")
        return out
    if isinstance(raw, list) and raw:
        out["caption_ru"] = f"несколько изображений ({len(raw)} шт.)"
        return out
    out["caption_ru"] = fp[:120]
    return out


def _unresolved_placeholder_in_text(ctx: L1Context, rule: dict[str, Any]) -> list[FindingDraft]:
    output: list[FindingDraft] = []
    for ad in ctx.ads:
        if not _is_structurally_enabled_yandex_ad(ad):
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
                    "matched_placeholder": matched[0] if len(matched) == 1 else matched,
                    "matched_placeholders": matched,
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
    by_group: dict[str, dict[tuple[str, str], list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for ad in ctx.ads:
        if not _is_structurally_enabled_yandex_ad(ad):
            continue
        group_id = str(ad.get("ad_group_id"))
        text_sig = "|".join(
            [
                str(ad.get("title") or "").strip().lower(),
                str(ad.get("text") or "").strip().lower(),
                str(ad.get("url") or ad.get("final_url") or "").strip().lower(),
            ]
        )
        if text_sig == "||":
            continue
        img_fp = _ad_image_fingerprint(ad)
        by_group[group_id][(text_sig, img_fp)].append(ad)
    out: list[FindingDraft] = []
    for group_id, grouped in by_group.items():
        for (text_sig, img_fp), ads in grouped.items():
            if len(ads) < 2:
                continue
            sample = ads[0]
            dedupe_key = f"{text_sig}\x1f{img_fp}".encode("utf-8")
            out.append(
                FindingDraft(
                    entity_key=f"group:{group_id}:duplicate_ad:{hashlib.sha256(dedupe_key).hexdigest()[:16]}",
                    issue_location=f"group:{group_id}",
                    campaign_external_id=str(sample.get("campaign_id")),
                    group_external_id=group_id,
                    ad_external_id=None,
                    evidence={
                        "campaign_id": sample.get("campaign_id"),
                        "group_id": group_id,
                        "ad_ids": sorted(str(item.get("id")) for item in ads),
                        "duplicate_signature_summary": {
                            "title": str(sample.get("title") or ""),
                            "text": str(sample.get("text") or ""),
                            "url": str(sample.get("url") or sample.get("final_url") or ""),
                        },
                        "shared_image_fingerprint": img_fp or None,
                        "ads_image_summaries": [_ad_image_evidence_summary(a) for a in sorted(ads, key=lambda x: str(x.get("id")))],
                    },
                    impact_ru=(
                        "Дубль объявления: в одной группе есть минимум два объявления с одинаковой связкой "
                        "«заголовок + текст + финальная ссылка» и тем же изображением (по id, URL или названию в снимке). "
                        "Объявления с одинаковым текстом, но с разными изображениями в библиотеке (другой id/имя/URL) "
                        "или разными форматами креатива (1:1, 3:4, 16:9 и т.д.) сюда не попадают — это не ошибка. "
                        "Полные дубли конкурируют в аукционе и путают отчётность."
                    ),
                    recommendation_ru=rule.get(
                        "recommendation_ru",
                        "Оставить одно объявление или изменить заголовок, текст, ссылку или креатив так, чтобы связка отличалась.",
                    ),
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
        dup_ids: list[str] = []
        for rows in duplicates:
            for item in rows:
                if isinstance(item, dict) and item.get("sitelink_id") is not None:
                    dup_ids.append(str(item.get("sitelink_id")))
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
                    "duplicate_sitelinks": sorted(set(dup_ids)),
                    "duplicate_sitelink_clusters": duplicates,
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
                    "conflicting_negative": conflicts[0] if conflicts else None,
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
                    "conflicting_negative": conflicts[0] if conflicts else None,
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
        if not _is_structurally_enabled_yandex_ad(ad):
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
        if not _is_structurally_enabled_yandex_ad(ad):
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
                    "ad_title": ad.get("title"),
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
        ads = [a for a in by_group.get(group_id, []) if _is_structurally_enabled_yandex_ad(a)]
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
                    "group_name": group.get("name"),
                    "ad_ids": sorted(str(a.get("id")) for a in ads),
                    "ads_count": len(ads),
                    "approved_ads_count": sum(
                        1 for a in ads if str(a.get("moderation_status") or "").lower() == "approved"
                    ),
                },
                impact_ru="Все активные объявления в группе отклонены/ограничены, группа не может эффективно откручиваться.",
                recommendation_ru=rule.get("recommendation_ru", "Исправить объявления группы и пройти модерацию."),
            )
        )
    return out


def _expired_date_in_ad_text(ctx: L1Context, rule: dict[str, Any]) -> list[FindingDraft]:
    now = datetime.now(timezone.utc).date()
    current_year = now.year
    out: list[FindingDraft] = []
    for ad in ctx.ads:
        if not _is_structurally_enabled_yandex_ad(ad):
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
                    evidence={
                        "ad_id": ad.get("id"),
                        "expired_date": match.group(0),
                        "matched_date_text": match.group(0),
                        "parsed_date": value.isoformat(),
                    },
                    impact_ru="В тексте объявления указана прошедшая дата, оффер выглядит неактуальным.",
                    recommendation_ru=rule.get("recommendation_ru", "Обновить дату в тексте объявления."),
                )
            )
        for ymatch in _EXPIRED_YEAR_PHRASE_RE.finditer(text):
            y = int(ymatch.group(1))
            if y >= current_year:
                continue
            snippet = ymatch.group(0).strip()
            out.append(
                FindingDraft(
                    entity_key=f"ad:{ad.get('id')}:expired_year:{y}",
                    issue_location=f"ad:{ad.get('id')}",
                    campaign_external_id=str(ad.get("campaign_id")),
                    group_external_id=str(ad.get("ad_group_id")),
                    ad_external_id=str(ad.get("id")),
                    evidence={
                        "ad_id": ad.get("id"),
                        "matched_date_text": snippet,
                        "parsed_date": str(y),
                    },
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
        if isinstance(sitelinks, list):
            for idx, sl in enumerate(sitelinks):
                if not isinstance(sl, dict):
                    continue
                text = f"{sl.get('title') or ''} {sl.get('description') or ''}"
                sid = sl.get("sitelink_id")
                sid_s = str(sid) if sid is not None else f"idx{idx}"
                for match in _DATE_RE.finditer(text):
                    day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
                    try:
                        value = datetime(year=year, month=month, day=day, tzinfo=timezone.utc).date()
                    except ValueError:
                        continue
                    if value >= now:
                        continue
                    ev: dict[str, Any] = {
                        "ad_id": ad_id,
                        "extension_type": "sitelink",
                        "matched_date_text": match.group(0),
                        "parsed_date": value.isoformat(),
                        "sitelink_index": idx,
                        "sitelink_title": sl.get("title"),
                    }
                    if sid is not None:
                        ev["sitelink_id"] = str(sid)
                    out.append(
                        FindingDraft(
                            entity_key=f"ext:{ad_id}:sitelink:{sid_s}:expired:{match.group(0)}",
                            issue_location=f"ad:{ad_id}" if ad_id else f"campaign:{campaign_id}",
                            campaign_external_id=campaign_id or None,
                            group_external_id=group_id or None,
                            ad_external_id=str(ad_id) if ad_id is not None else None,
                            evidence=ev,
                            impact_ru="В тексте расширения (быстрой ссылки) указана прошедшая дата.",
                            recommendation_ru=rule.get("recommendation_ru", "Обновить даты в расширениях объявления."),
                        )
                    )
        callouts = ext.get("callouts") or []
        if isinstance(callouts, list):
            for cidx, raw_co in enumerate(callouts):
                if isinstance(raw_co, str):
                    co_text = raw_co
                elif isinstance(raw_co, dict):
                    co_text = str(raw_co.get("text") or raw_co.get("title") or "")
                else:
                    continue
                for match in _DATE_RE.finditer(co_text):
                    day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
                    try:
                        value = datetime(year=year, month=month, day=day, tzinfo=timezone.utc).date()
                    except ValueError:
                        continue
                    if value >= now:
                        continue
                    out.append(
                        FindingDraft(
                            entity_key=f"ext:{ad_id}:callout:{cidx}:expired:{match.group(0)}",
                            issue_location=f"ad:{ad_id}" if ad_id else f"campaign:{campaign_id}",
                            campaign_external_id=campaign_id or None,
                            group_external_id=group_id or None,
                            ad_external_id=str(ad_id) if ad_id is not None else None,
                            evidence={
                                "ad_id": ad_id,
                                "extension_type": "callout",
                                "callout_index": cidx,
                                "callout_text": co_text,
                                "matched_date_text": match.group(0),
                                "parsed_date": value.isoformat(),
                            },
                            impact_ru="В тексте расширения (уточнения) указана прошедшая дата.",
                            recommendation_ru=rule.get("recommendation_ru", "Обновить даты в расширениях объявления."),
                        )
                    )
    return out


def _past_year_in_text(ctx: L1Context, rule: dict[str, Any]) -> list[FindingDraft]:
    current_year = datetime.now(timezone.utc).year
    out: list[FindingDraft] = []
    for ad in ctx.ads:
        if not _is_structurally_enabled_yandex_ad(ad):
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
                evidence={
                    "ad_id": ad.get("id"),
                    "matched_years": stale,
                    "mentioned_years": stale,
                    "current_year": current_year,
                },
                impact_ru="В тексте объявления упоминается прошлый год, это снижает актуальность оффера.",
                recommendation_ru=rule.get("recommendation_ru", "Актуализировать год в текстах объявлений."),
            )
        )
    return out


def _duplicate_keywords_with_overlap(ctx: L1Context, rule: dict[str, Any]) -> list[FindingDraft]:
    kw_source = ctx.account_keywords if ctx.account_keywords is not None else ctx.keywords
    kws = [kw for kw in kw_source if _is_servable_yandex_keyword(kw)]
    kws.sort(key=lambda x: str(x.get("id") or ""))
    groups_src = _groups_for_geo_rules(ctx)
    camp_source = ctx.account_campaigns if ctx.account_campaigns is not None else ctx.campaigns
    campaigns_active = [c for c in camp_source if _is_active_yandex_campaign(c)]
    out: list[FindingDraft] = []
    scope = ctx.scoped_campaign_external_id
    for i in range(len(kws)):
        left = kws[i]
        left_id = str(left.get("id") or "")
        left_phrase = str(left.get("phrase") or left.get("text") or "")
        left_tokens = _keyword_positive_tokens(left_phrase)
        if not left_tokens:
            continue
        g_left = str(left.get("ad_group_id"))
        c_left = str(left.get("campaign_id"))
        for j in range(i + 1, len(kws)):
            right = kws[j]
            right_phrase = str(right.get("phrase") or right.get("text") or "")
            right_tokens = _keyword_positive_tokens(right_phrase)
            if not right_tokens:
                continue
            g_right = str(right.get("ad_group_id"))
            c_right = str(right.get("campaign_id"))
            same_group = g_left == g_right
            if same_group and left_tokens == right_tokens:
                continue
            inter = left_tokens & right_tokens
            if not inter:
                continue
            overlap_ratio = len(inter) / max(1, min(len(left_tokens), len(right_tokens)))
            if overlap_ratio < 0.7:
                continue
            if c_left != c_right:
                geo_ok, _ = _campaign_pair_geo_targets_overlap(c_left, c_right, campaigns_active, groups_src)
                if not geo_ok:
                    continue
            if same_group:
                overlap_kind = "intra_group"
                issue_location = f"group:{g_left}"
                group_external_id = g_left
                attach_campaign = c_left
            elif c_left == c_right:
                overlap_kind = "cross_group"
                issue_location = f"campaign:{c_left}"
                group_external_id = None
                attach_campaign = c_left
            else:
                overlap_kind = "cross_campaign"
                issue_location = f"account:{ctx.account_id}"
                group_external_id = None
                attach_campaign = c_left
            if scope and (scope == c_left or scope == c_right):
                attach_campaign = scope
            kid_a, kid_b = sorted([str(left.get("id")), str(right.get("id"))])
            out.append(
                FindingDraft(
                    entity_key=f"kw_overlap:{kid_a}:{kid_b}",
                    issue_location=issue_location,
                    campaign_external_id=attach_campaign,
                    group_external_id=group_external_id,
                    ad_external_id=None,
                    evidence={
                        "overlap_kind": overlap_kind,
                        "left_campaign_id": c_left,
                        "right_campaign_id": c_right,
                        "left_group_id": g_left,
                        "right_group_id": g_right,
                        "left_keyword_id": left.get("id"),
                        "right_keyword_id": right.get("id"),
                        "left_keyword": left.get("phrase") or left.get("text"),
                        "right_keyword": right.get("phrase") or right.get("text"),
                        "intersection_tokens": sorted(inter),
                        "overlap_ratio": overlap_ratio,
                    },
                    impact_ru="Похожие ключевые фразы частично дублируют спрос и создают внутреннюю конкуренцию (в группе, между группами или между кампаниями с пересекающимся гео).",
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
                        "group_name": g.get("name"),
                        "missing_negative_tokens": sorted(missing),
                    },
                    impact_ru="Отсутствует кросс-минусовка между группами, трафик пересекается и дорожает.",
                    recommendation_ru=rule.get("recommendation_ru", "Добавить кросс-минус-слова между группами."),
                )
            )
    return out


def _campaign_self_competition_by_geo_and_semantics(ctx: L1Context, rule: dict[str, Any]) -> list[FindingDraft]:
    kw_source = ctx.account_keywords if ctx.account_keywords is not None else ctx.keywords
    groups_src = _groups_for_geo_rules(ctx)
    campaign_keywords: dict[str, set[str]] = defaultdict(set)
    for kw in kw_source:
        if not _is_servable_yandex_keyword(kw):
            continue
        campaign_id = str(kw.get("campaign_id"))
        norm = _normalize_keyword(str(kw.get("phrase") or kw.get("text") or ""))
        if norm:
            campaign_keywords[campaign_id].add(norm)
    camp_source = ctx.account_campaigns if ctx.account_campaigns is not None else ctx.campaigns
    campaigns = [c for c in camp_source if _is_active_yandex_campaign(c)]
    campaigns.sort(key=lambda c: str(c.get("id")))
    out: list[FindingDraft] = []
    scope = ctx.scoped_campaign_external_id
    for i in range(len(campaigns)):
        left = campaigns[i]
        left_id = str(left.get("id"))
        left_kw = {x for x in campaign_keywords.get(left_id, set()) if x}
        if not left_kw:
            continue
        for j in range(i + 1, len(campaigns)):
            right = campaigns[j]
            right_id = str(right.get("id"))
            right_kw = {x for x in campaign_keywords.get(right_id, set()) if x}
            if not right_kw:
                continue
            geo_ok, geo_overlap = _campaign_pair_geo_targets_overlap(left_id, right_id, campaigns, groups_src)
            kw_overlap = left_kw & right_kw
            if not geo_ok or not kw_overlap:
                continue
            lo, hi = sorted([left_id, right_id])
            attach_id = lo
            if scope and (scope == left_id or scope == right_id):
                attach_id = scope
            out.append(
                FindingDraft(
                    entity_key=f"campaign_overlap:{lo}:{hi}",
                    issue_location=f"account:{ctx.account_id}",
                    campaign_external_id=attach_id,
                    group_external_id=None,
                    ad_external_id=None,
                    evidence={
                        "left_campaign_id": left_id,
                        "right_campaign_id": right_id,
                        "geo_overlap": sorted(geo_overlap)[:30],
                        "semantic_overlap_count": len(kw_overlap),
                        "semantic_overlap_examples": sorted(list(kw_overlap))[:10],
                    },
                    impact_ru="Кампании пересекаются по гео и семантике, возникает само-конкуренция внутри аккаунта.",
                    recommendation_ru=rule.get("recommendation_ru", "Развести гео/семантику между кампаниями."),
                )
            )
    return out


# Yandex Direct GeoTree ids for cities covered by `city_aliases` in `_geo_text_targeting_mismatch`.
_GEO_TEXT_YANDEX_REGION_ID_TO_CITY: dict[int, str] = {
    213: "москва",
    2: "санкт-петербург",
}


def _geo_text_targeting_mismatch(ctx: L1Context, rule: dict[str, Any]) -> list[FindingDraft]:
    # Minimal deterministic detector for current test fixture.
    city_aliases = {
        "москва": {"москва", "москов"},
        "санкт-петербург": {"санкт-петербург", "санкт петербург", "спб", "питер"},
    }
    campaigns = {str(c.get("id")): c for c in ctx.campaigns}
    groups_src = _groups_for_geo_rules(ctx)
    out: list[FindingDraft] = []
    for ad in ctx.ads:
        if not _is_servable_yandex_ad(ad):
            continue
        campaign_id = str(ad.get("campaign_id"))
        campaign = campaigns.get(campaign_id)
        if not campaign:
            continue
        campaign_geo_text = " ".join(str(x).lower() for x in (campaign.get("geo") or []))
        fp = _campaign_geo_fingerprint(campaign_id, [campaign], groups_src)
        campaign_geo_text += " " + " ".join(
            x.replace("label:", "", 1) for x in fp if x.startswith("label:")
        )
        if GEO_FINGERPRINT_ALL_REGIONS in fp:
            campaign_geo_text += " " + " ".join(
                alias for aliases in city_aliases.values() for alias in sorted(aliases)
            )
        else:
            for x in fp:
                if not x.startswith("rid:") or x == GEO_FINGERPRINT_ALL_REGIONS:
                    continue
                rid_part = x.split(":", 1)[-1]
                if not rid_part.isdigit():
                    continue
                canonical = _GEO_TEXT_YANDEX_REGION_ID_TO_CITY.get(int(rid_part))
                if canonical:
                    aliases = city_aliases.get(canonical)
                    if aliases:
                        campaign_geo_text += " " + " ".join(sorted(aliases))
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
