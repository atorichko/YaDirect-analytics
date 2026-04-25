from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qsl, urlparse

from app.services.l1_rules import FindingDraft
from app.services.yandex_direct_dynamic_url import (
    filter_non_yandex_placeholders,
    normalize_query_value_for_yandex_macros,
    utm_pairs_with_yandex_macro_normalization,
)

_TECH_VALUES = {"", "undefined", "null", "none", "(not set)"}
_PLACEHOLDER_RE = re.compile(r"(\{\{[^{}]+\}\}|\{[^{}]+\}|%[^%]+%|\[[^\[\]]+\]|<[^<>]+>)")
# utm_content / utm_term often differ on purpose (объявление vs быстрые ссылки).
_STRICT_UTM_KEYS = frozenset({"utm_source", "utm_medium", "utm_campaign"})


@dataclass(slots=True)
class L3Context:
    account_id: str
    ads: list[dict[str, Any]]
    extensions: list[dict[str, Any]]
    campaigns: list[dict[str, Any]] = field(default_factory=list)
    groups: list[dict[str, Any]] = field(default_factory=list)


L3RuleHandler = Callable[[L3Context, dict[str, Any]], list[FindingDraft]]


def _iter_ad_url_targets(ad: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    main_url = ad.get("url") or ad.get("final_url")
    if isinstance(main_url, str) and main_url.strip():
        rows.append(
            {
                "field": "ad.url",
                "url": main_url.strip(),
                "sitelink_id": None,
                "health": ad.get("url_health") or {},
            }
        )
    sitelinks = ad.get("sitelinks") or []
    if isinstance(sitelinks, list):
        for idx, item in enumerate(sitelinks):
            if not isinstance(item, dict):
                continue
            url = item.get("url")
            if not isinstance(url, str) or not url.strip():
                continue
            sid = item.get("sitelink_id")
            rows.append(
                {
                    "field": f"ad.sitelinks[{idx}].url",
                    "url": url.strip(),
                    "sitelink_id": str(sid) if sid is not None and str(sid) else None,
                    "health": item.get("url_health") or {},
                }
            )
    return rows


def _collect_ad_urls(ad: dict[str, Any]) -> list[tuple[str, str, str | None]]:
    return [(r["field"], r["url"], r["sitelink_id"]) for r in _iter_ad_url_targets(ad)]


def _tracking_like_urls_from_entity(entity: dict[str, Any]) -> list[str]:
    """URL-поля кампании/группы, где может быть задана UTM-разметка (шаблон ссылки)."""
    keys = (
        "tracking_url",
        "tracking_template",
        "campaign_tracking_url",
        "mobile_app_tracking_url",
        "href",
    )
    out: list[str] = []
    for k in keys:
        v = entity.get(k)
        if isinstance(v, str) and v.strip().startswith(("http://", "https://")):
            out.append(v.strip())
    return out


def _campaign_or_group_covers_required_utm(ctx: L3Context, ad: dict[str, Any], required: list[str]) -> bool:
    """True, если на уровне кампании или группы объявления есть URL со всеми обязательными UTM."""
    if not required:
        return False
    cid = str(ad.get("campaign_id") or "")
    gid = str(ad.get("ad_group_id") or "")
    for camp in ctx.campaigns:
        if str(camp.get("id")) != cid:
            continue
        for u in _tracking_like_urls_from_entity(camp):
            parsed = urlparse(u)
            pairs = utm_pairs_with_yandex_macro_normalization(parse_qsl(parsed.query, keep_blank_values=True))
            params = {k.lower(): v for k, v in pairs}
            if all(p.lower() in params for p in required):
                return True
    for grp in ctx.groups:
        if str(grp.get("id")) != gid:
            continue
        gc = str(grp.get("campaign_id") or "")
        if cid and gc and gc != cid:
            continue
        for u in _tracking_like_urls_from_entity(grp):
            parsed = urlparse(u)
            pairs = utm_pairs_with_yandex_macro_normalization(parse_qsl(parsed.query, keep_blank_values=True))
            params = {k.lower(): v for k, v in pairs}
            if all(p.lower() in params for p in required):
                return True
    return False


def _url_syntax_issues(url: str, parsed) -> list[str]:
    issues: list[str] = []
    scheme = (parsed.scheme or "").lower()
    if scheme not in {"http", "https"}:
        raw_scheme = (parsed.scheme or "").strip()
        if raw_scheme:
            issues.append(f"схема: ожидались http/https, фактически «{raw_scheme}»")
        else:
            issues.append("схема: отсутствует или не распознана (ожидались http/https)")
    netloc = (parsed.netloc or "").strip()
    if scheme in {"http", "https"} and not netloc:
        rest = (parsed.path or "").lstrip("/")
        if rest:
            issues.append(f"хост: пустой; похоже, адрес уехал в путь («{rest[:80]}»)")
        else:
            issues.append("хост: не указан (пустой netloc)")
    if " " in url and scheme not in {"http", "https"}:
        issues.append("в строке есть пробелы — URL должен быть закодирован")
    return issues


def _redirect_hop_count(chain: list[Any]) -> int:
    if not chain:
        return 0
    return max(0, len(chain) - 1)


def _redirect_chain_flow_ru(chain: list[Any]) -> str | None:
    """Кратко: какой URL на какой ведёт по шагам (для карточки находки)."""
    urls = [str(x).strip() for x in chain if str(x).strip()]
    if len(urls) < 2:
        return None
    parts = [f"{urls[i]} ведёт на {urls[i + 1]}" for i in range(len(urls) - 1)]
    return "; ".join(parts) + "."


def _url_query_highlight_all_bad(url: str) -> list[dict[str, Any]]:
    """Вся query-строка помечается как проблемная (удобно для UTM/синтаксиса)."""
    if "?" not in url:
        return [{"text": url, "ok": False}]
    base, rest = url.split("?", 1)
    return [{"text": f"{base}?", "ok": True}, {"text": rest, "ok": False}]


def _url_placeholder_highlight(value: str, placeholders: list[str]) -> list[dict[str, Any]]:
    if not placeholders:
        return [{"text": value, "ok": True}]
    bad = sorted(set(placeholders), key=len, reverse=True)
    segments: list[dict[str, Any]] = []
    cursor = 0
    n = len(value)
    while cursor < n:
        earliest: tuple[int, int, str] | None = None
        for ph in bad:
            pos = value.find(ph, cursor)
            if pos < 0:
                continue
            end = pos + len(ph)
            cand = (pos, end, ph)
            if earliest is None or pos < earliest[0]:
                earliest = cand
        if earliest is None:
            segments.append({"text": value[cursor:], "ok": True})
            break
        pos, end, ph = earliest
        if pos > cursor:
            segments.append({"text": value[cursor:pos], "ok": True})
        segments.append({"text": ph, "ok": False})
        cursor = end
    return segments


def _account_utm_main_url_fingerprint(url: str) -> str:
    """Грубая сигнатура разметки по основной ссылке объявления (для сверки в масштабе аккаунта)."""
    parsed = urlparse(url.strip())
    if parsed.scheme not in {"http", "https"}:
        return "scheme:not_http"
    raw_q = parsed.query or ""
    raw_pairs = utm_pairs_with_yandex_macro_normalization(parse_qsl(raw_q, keep_blank_values=True))
    errs = _utm_error_codes(raw_q, raw_pairs)
    if errs:
        return f"broken:{','.join(errs[:4])}"
    d = {k.lower(): str(v).strip() for k, v in raw_pairs}
    parts: list[str] = []
    for key in sorted(_STRICT_UTM_KEYS):
        v = d.get(key, "")
        vl = v.strip().lower()
        if not vl or vl in _TECH_VALUES:
            parts.append(f"{key}:∅")
        else:
            parts.append(f"{key}:{vl[:64]}")
    return "utm|" + "|".join(parts)


def _inconsistent_utm_account_wide(ctx: L3Context, rule: dict[str, Any]) -> list[FindingDraft]:
    if not rule.get("account_wide_utm", True):
        return []
    buckets: dict[str, dict[str, Any]] = {}
    for ad in ctx.ads:
        main = ad.get("url") or ad.get("final_url")
        if not isinstance(main, str) or not main.strip():
            continue
        cid = str(ad.get("campaign_id") or "")
        fp = _account_utm_main_url_fingerprint(main.strip())
        if fp not in buckets:
            buckets[fp] = {"sample_url": main.strip(), "campaigns": set()}
        buckets[fp]["campaigns"].add(cid)
    if len(buckets) < 2:
        return []
    all_camps: set[str] = set()
    for b in buckets.values():
        all_camps |= b["campaigns"]
    if len(all_camps) < 2:
        return []
    pattern_samples = {k: buckets[k]["sample_url"] for k in sorted(buckets.keys())[:12]}
    return [
        FindingDraft(
            entity_key=f"account:{ctx.account_id}:utm_pattern_mixed",
            issue_location=f"account:{ctx.account_id}",
            campaign_external_id=None,
            group_external_id=None,
            ad_external_id=None,
            evidence={
                "scope": "account",
                "account_id": ctx.account_id,
                "distinct_utm_patterns": sorted(buckets.keys()),
                "pattern_sample_urls": pattern_samples,
                "campaigns_with_mixed_patterns": sorted(all_camps),
                "issue_explanation_ru": (
                    "В аккаунте в разных кампаниях используются несовместимые шаблоны UTM "
                    "(отличаются utm_source / utm_medium / utm_campaign, встречаются укороченные "
                    "или повреждённые варианты). Из-за этого нельзя корректно сводить статистику "
                    "в одной воронке."
                ),
            },
            impact_ru="Фрагментированная UTM-разметка ломает сводную аналитику по аккаунту.",
            recommendation_ru=rule.get(
                "recommendation_ru",
                "Утвердить единый шаблон UTM и выровнять ссылки во всех кампаниях.",
            ),
        )
    ]


def _utm_error_codes(raw_query: str, raw_pairs: list[tuple[str, str]]) -> list[str]:
    codes: list[str] = []
    if "&&" in raw_query or ";&&" in raw_query or raw_query.strip().startswith("&"):
        codes.append("malformed_separator")
    keys_lower = [k.lower() for k, _ in raw_pairs]
    for k, v in raw_pairs:
        lk = k.lower() if k else ""
        if k == "" or lk == "":
            codes.append("empty_param_name")
            continue
        v_norm = normalize_query_value_for_yandex_macros(str(v))
        if str(v_norm).strip().lower() in _TECH_VALUES:
            codes.append(f"empty_value:{lk}")
    for lk in sorted({x for x in keys_lower if x}):
        if keys_lower.count(lk) > 1:
            codes.append(f"duplicate_param:{lk}")
    # preserve stable order: malformed first, then alphabetical by code string
    return sorted(set(codes), key=lambda x: (not x.startswith("malformed"), x))


def _base_finding(ad: dict[str, Any], entity_key: str, issue_location: str, evidence: dict, recommendation: str, impact: str) -> FindingDraft:
    return FindingDraft(
        entity_key=entity_key,
        issue_location=issue_location,
        campaign_external_id=str(ad.get("campaign_id")) if ad.get("campaign_id") is not None else None,
        group_external_id=str(ad.get("ad_group_id")) if ad.get("ad_group_id") is not None else None,
        ad_external_id=str(ad.get("id")) if ad.get("id") is not None else None,
        evidence=evidence,
        impact_ru=impact,
        recommendation_ru=recommendation,
    )


def _invalid_url_syntax(ctx: L3Context, rule: dict[str, Any]) -> list[FindingDraft]:
    out: list[FindingDraft] = []
    for ad in ctx.ads:
        for field, value, sitelink_id in _collect_ad_urls(ad):
            parsed = urlparse(value)
            if parsed.scheme in {"http", "https"} and parsed.netloc:
                continue
            parts: list[dict[str, Any]] = [{"text": value, "ok": False}]
            if value.startswith("http://") or value.startswith("https://"):
                split_at = value.find("://") + 3
                head, tail = value[:split_at], value[split_at:]
                parts = [{"text": head, "ok": True}, {"text": tail, "ok": False}]
            issues = _url_syntax_issues(value, parsed)
            ek = f"ad:{ad.get('id')}:{field}:invalid_url"
            if sitelink_id:
                ek = f"ad:{ad.get('id')}:sl:{sitelink_id}:invalid_url"
            ev: dict[str, Any] = {
                "ad_id": ad.get("id"),
                "url_field": field,
                "url_value": value,
                "display_url_full": value,
                "validation_error": "invalid_syntax",
                "url_syntax_issues": issues,
                "url_value_segments": parts,
                "full_url_highlight_segments": parts,
                "issue_explanation_ru": (
                    "URL не соответствует ожидаемому формату (схема http/https, хост, кодировка). "
                    "Клик может не открыть нужную страницу."
                ),
            }
            if sitelink_id:
                ev["sitelink_id"] = sitelink_id
            out.append(
                _base_finding(
                    ad,
                    entity_key=ek,
                    issue_location=f"ad:{ad.get('id')}",
                    evidence=ev,
                    recommendation=rule.get("recommendation_ru", "Исправить формат URL."),
                    impact="Некорректный URL ломает переходы и трафик.",
                )
            )
    return out


def _missing_required_utm(ctx: L3Context, rule: dict[str, Any]) -> list[FindingDraft]:
    required = [str(x) for x in rule.get("required_utm_params", []) if str(x)]
    out: list[FindingDraft] = []
    for ad in ctx.ads:
        for field, value, sitelink_id in _collect_ad_urls(ad):
            parsed = urlparse(value)
            pairs_cmp = utm_pairs_with_yandex_macro_normalization(parse_qsl(parsed.query, keep_blank_values=True))
            params = {k.lower(): v for k, v in pairs_cmp}
            missing = [param for param in required if param.lower() not in params]
            if not missing:
                continue
            if _campaign_or_group_covers_required_utm(ctx, ad, required):
                continue
            ek = f"ad:{ad.get('id')}:{field}:missing_utm"
            if sitelink_id:
                ek = f"ad:{ad.get('id')}:sl:{sitelink_id}:missing_utm"
            ev: dict[str, Any] = {
                "ad_id": ad.get("id"),
                "url_field": field,
                "checked_url": value,
                "display_url_full": value,
                "url_query_highlight_segments": _url_query_highlight_all_bad(value),
                "missing_utm_params": missing,
                "utm_param_status": [
                    {"param": p, "present": p.lower() in params, "value": params.get(p.lower())} for p in required
                ],
                "issue_explanation_ru": (
                    "В финальном URL не хватает обязательных UTM-параметров из политики аккаунта, "
                    "и полный набор этих параметров не найден ни в ссылке объявления/быстрой ссылки, "
                    "ни в URL-полях уровня кампании или группы (tracking_url, tracking_template и т.п.). "
                    "В отчётах аналитики кампания и объявление не сопоставляются с источником трафика."
                ),
            }
            if sitelink_id:
                ev["sitelink_id"] = sitelink_id
            out.append(
                _base_finding(
                    ad,
                    entity_key=ek,
                    issue_location=f"ad:{ad.get('id')}",
                    evidence=ev,
                    recommendation=rule.get("recommendation_ru", "Добавить обязательные UTM-параметры."),
                    impact="Без обязательных UTM нарушается сквозная аналитика и атрибуция.",
                )
            )
    return out


def _invalid_utm(ctx: L3Context, rule: dict[str, Any]) -> list[FindingDraft]:
    out: list[FindingDraft] = []
    for ad in ctx.ads:
        for field, value, sitelink_id in _collect_ad_urls(ad):
            parsed = urlparse(value)
            raw_q = parsed.query or ""
            raw_pairs = parse_qsl(raw_q, keep_blank_values=True)
            pairs_cmp = utm_pairs_with_yandex_macro_normalization(raw_pairs)
            err_codes = _utm_error_codes(raw_q, pairs_cmp)
            if not err_codes:
                continue
            details: list[dict[str, str]] = []
            for code in err_codes:
                if code.startswith("empty_value:"):
                    param = code.split(":", 1)[1]
                    details.append({"code": code, "param": param, "issue": "пустое или техническое значение"})
                elif code.startswith("duplicate_param:"):
                    param = code.split(":", 1)[1]
                    details.append({"code": code, "param": param, "issue": "параметр встречается несколько раз"})
                elif code == "malformed_separator":
                    details.append({"code": code, "param": "", "issue": "лишние «&» или разорванная query-строка"})
                elif code == "empty_param_name":
                    details.append({"code": code, "param": "", "issue": "пустое имя параметра (часто из-за «&&»)"})
            ek = f"ad:{ad.get('id')}:{field}:invalid_utm"
            if sitelink_id:
                ek = f"ad:{ad.get('id')}:sl:{sitelink_id}:invalid_utm"
            ev: dict[str, Any] = {
                "ad_id": ad.get("id"),
                "url_field": field,
                "checked_url": value,
                "display_url_full": value,
                "url_query_highlight_segments": _url_query_highlight_all_bad(value),
                "utm_validation_errors": err_codes,
                "utm_issue_details": details,
                "issue_explanation_ru": (
                    "Строка запроса URL содержит ошибки UTM: пустые значения, дубли параметров или "
                    "некорректные разделители. Часть кликов уйдёт в аналитику с битыми метками."
                ),
            }
            if sitelink_id:
                ev["sitelink_id"] = sitelink_id
            out.append(
                _base_finding(
                    ad,
                    entity_key=ek,
                    issue_location=f"ad:{ad.get('id')}",
                    evidence=ev,
                    recommendation=rule.get("recommendation_ru", "Исправить структуру UTM-разметки."),
                    impact="Некорректная UTM-разметка искажает отчеты и усложняет аналитику.",
                )
            )
    return out


def _main_and_sitelink_domains_mismatch(ctx: L3Context, rule: dict[str, Any]) -> list[FindingDraft]:
    out: list[FindingDraft] = []
    for ad in ctx.ads:
        main_url = ad.get("url") or ad.get("final_url")
        if not isinstance(main_url, str) or not main_url:
            continue
        main_domain = urlparse(main_url).netloc.lower()
        sitelinks = ad.get("sitelinks") or []
        rows: list[dict[str, Any]] = []
        mismatch_domains: list[str] = []
        for item in sitelinks:
            if not isinstance(item, dict) or not isinstance(item.get("url"), str):
                continue
            surl = str(item["url"]).strip()
            dom = urlparse(surl).netloc.lower()
            sid = item.get("sitelink_id")
            same = bool(dom and dom == main_domain)
            rows.append(
                {
                    "sitelink_id": str(sid) if sid is not None else None,
                    "url": surl,
                    "domain": dom,
                    "matches_main_domain": same,
                }
            )
            if dom and dom != main_domain:
                mismatch_domains.append(dom)
        if not mismatch_domains:
            continue
        out.append(
            _base_finding(
                ad,
                entity_key=f"ad:{ad.get('id')}:domain_mismatch",
                issue_location=f"ad:{ad.get('id')}",
                evidence={
                    "ad_id": ad.get("id"),
                    "main_url": main_url.strip(),
                    "main_url_display": main_url.strip(),
                    "main_domain": main_domain,
                    "sitelink_urls": rows,
                    "sitelink_urls_mismatched": [r for r in rows if not r.get("matches_main_domain")],
                    "sitelink_domains": sorted(set(mismatch_domains)),
                    "urls_comparison_note_ru": (
                        "Ниже — основная ссылка объявления и быстрые ссылки с другим доменом."
                    ),
                },
                recommendation=rule.get("recommendation_ru", "Привести все ссылки объявления к согласованному домену."),
                impact="Разные домены в объявлении и быстрых ссылках ухудшают консистентность лендинга.",
            )
        )
    return out


def _empty_or_technical_url_params(ctx: L3Context, rule: dict[str, Any]) -> list[FindingDraft]:
    out: list[FindingDraft] = []
    for ad in ctx.ads:
        for field, value, sitelink_id in _collect_ad_urls(ad):
            parsed = urlparse(value)
            pairs = parse_qsl(parsed.query, keep_blank_values=True)
            bad: dict[str, str] = {}
            for k, v in pairs:
                if str(v).strip().lower() in _TECH_VALUES:
                    bad[str(k)] = str(v)
            if not bad:
                continue
            segments: list[dict[str, Any]] = []
            q = parsed.query
            if q:
                cursor = 0
                for k, v in pairs:
                    if str(v).strip().lower() not in _TECH_VALUES:
                        continue
                    needle = f"{k}={v}" if v != "" else f"{k}="
                    pos = q.find(needle, cursor)
                    if pos < 0:
                        needle = k + "="
                        pos = q.find(needle, cursor)
                    if pos >= 0:
                        pre = q[cursor:pos]
                        if pre:
                            segments.append({"text": pre, "ok": True})
                        seg_len = len(needle)
                        segments.append({"text": q[pos : pos + seg_len], "ok": False})
                        cursor = pos + seg_len
                if cursor < len(q):
                    segments.append({"text": q[cursor:], "ok": True})
            if not segments:
                segments = [{"text": parsed.query or value, "ok": False}]
            ek = f"ad:{ad.get('id')}:{field}:technical_params"
            if sitelink_id:
                ek = f"ad:{ad.get('id')}:sl:{sitelink_id}:technical_params"
            ev: dict[str, Any] = {
                "ad_id": ad.get("id"),
                "url_field": field,
                "checked_url": value,
                "display_url_full": value,
                "invalid_params": sorted(bad.keys()),
                "empty_or_technical_values": bad,
                "query_highlight_segments": segments,
                "issue_explanation_ru": (
                    "В query-строке есть параметры с пустыми или техническими значениями "
                    "(undefined, null и т.п.) — они засоряют отчёты и ломают сегментацию."
                ),
            }
            if sitelink_id:
                ev["sitelink_id"] = sitelink_id
            out.append(
                _base_finding(
                    ad,
                    entity_key=ek,
                    issue_location=f"ad:{ad.get('id')}",
                    evidence=ev,
                    recommendation=rule.get("recommendation_ru", "Удалить пустые или технические параметры из ссылки."),
                    impact="Технические параметры в URL ухудшают качество трекинга и могут ломать маршрутизацию.",
                )
            )
    return out


def _unresolved_placeholder_in_url(ctx: L3Context, rule: dict[str, Any]) -> list[FindingDraft]:
    out: list[FindingDraft] = []
    for ad in ctx.ads:
        for field, value, sitelink_id in _collect_ad_urls(ad):
            matched_all = _PLACEHOLDER_RE.findall(value)
            matched = filter_non_yandex_placeholders(matched_all)
            if not matched:
                continue
            ek = f"ad:{ad.get('id')}:{field}:placeholder"
            if sitelink_id:
                ek = f"ad:{ad.get('id')}:sl:{sitelink_id}:placeholder"
            ev: dict[str, Any] = {
                "ad_id": ad.get("id"),
                "url_field": field,
                "checked_url": value,
                "display_url_full": value,
                "url_highlight_segments": _url_placeholder_highlight(value, matched),
                "matched_placeholder": matched[0] if len(matched) == 1 else matched,
                "matched_placeholders": matched,
                "yandex_dynamic_placeholders_ignored_ru": (
                    "Плейсхолдеры подстановки Яндекс Директа `{…}` из официального списка динамических "
                    "параметров не считаются ошибкой и в список проблемных не попадают."
                ),
                "issue_explanation_ru": (
                    "В URL остался нераскрытый макрос/плейсхолдер — переход может вести на неверный адрес."
                ),
            }
            if sitelink_id:
                ev["sitelink_id"] = sitelink_id
            out.append(
                _base_finding(
                    ad,
                    entity_key=ek,
                    issue_location=f"ad:{ad.get('id')}",
                    evidence=ev,
                    recommendation=rule.get("recommendation_ru", "Исправить URL и удалить незаполненные шаблоны."),
                    impact="Незаполненные макросы в URL приводят к битым переходам и ошибкам аналитики.",
                )
            )
    return out


def _inconsistent_utm_within_each_ad(ctx: L3Context, rule: dict[str, Any]) -> list[FindingDraft]:
    """Разные utm_source / utm_medium / utm_campaign между URL одного объявления."""
    out: list[FindingDraft] = []
    for ad in ctx.ads:
        by_key: dict[str, set[str]] = {k: set() for k in _STRICT_UTM_KEYS}
        for _field, value, _sid in _collect_ad_urls(ad):
            parsed = urlparse(value)
            for k, v in utm_pairs_with_yandex_macro_normalization(
                parse_qsl(parsed.query, keep_blank_values=True)
            ):
                lk = k.lower()
                if lk not in _STRICT_UTM_KEYS:
                    continue
                vv = str(v).strip().lower()
                if vv in _TECH_VALUES:
                    continue
                by_key[lk].add(vv)
        conflicts = {key: sorted(vals) for key, vals in by_key.items() if len(vals) > 1}
        if not conflicts:
            continue
        out.append(
            _base_finding(
                ad,
                entity_key=f"ad:{ad.get('id')}:inconsistent_utm",
                issue_location=f"ad:{ad.get('id')}",
                evidence={
                    "ad_id": ad.get("id"),
                    "utm_conflicts": conflicts,
                    "issue_explanation_ru": (
                        "У основной ссылки и быстрых ссылок одного объявления расходятся ключевые UTM — "
                        "сессии нельзя надёжно сопоставить в одной цепочке."
                    ),
                },
                recommendation=rule.get(
                    "recommendation_ru",
                    "Унифицировать UTM-разметку между основной ссылкой и быстрыми ссылками.",
                ),
                impact="Разная UTM-разметка внутри одного объявления ломает сопоставление данных в аналитике.",
            )
        )
    return out


def _inconsistent_utm_pattern(ctx: L3Context, rule: dict[str, Any]) -> list[FindingDraft]:
    out = _inconsistent_utm_account_wide(ctx, rule)
    out.extend(_inconsistent_utm_within_each_ad(ctx, rule))
    return out


def _http_ssl_redirect_based_checks(ctx: L3Context, rule: dict[str, Any]) -> list[FindingDraft]:
    code = str(rule.get("rule_code", ""))
    max_hops = int(rule.get("max_redirect_hops") or 5)
    out: list[FindingDraft] = []

    if code == "BROKEN_SITELINK_URL":
        for ad in ctx.ads:
            broken = [item for item in (ad.get("sitelinks") or []) if isinstance(item, dict) and item.get("url_health_error")]
            if not broken:
                continue
            ids = [str(x.get("sitelink_id")) for x in broken if x.get("sitelink_id") is not None]
            broken_rows = [
                {"sitelink_id": str(x.get("sitelink_id")), "url": x.get("url")} for x in broken if isinstance(x, dict)
            ]
            out.append(
                _base_finding(
                    ad,
                    entity_key=f"ad:{ad.get('id')}:{code.lower()}",
                    issue_location=f"ad:{ad.get('id')}",
                    evidence={
                        "broken_sitelink_urls": broken_rows,
                        "broken_quick_links_note_ru": "Битые быстрые ссылки (URL):",
                        "ad_id": ad.get("id"),
                        "broken_sitelinks": ids,
                    },
                    recommendation=rule.get("recommendation_ru", "Исправить ссылку."),
                    impact="Проблемы URL/редиректов/SSL ведут к потере трафика и конверсий.",
                )
            )
        return out

    for ad in ctx.ads:
        for tgt in _iter_ad_url_targets(ad):
            field = str(tgt["field"])
            source_url = str(tgt["url"])
            health = tgt["health"] if isinstance(tgt["health"], dict) else {}
            sitelink_id = tgt.get("sitelink_id")
            if code == "FINAL_DOMAIN_DIFFERS_AFTER_REDIRECT" and sitelink_id:
                continue

            status_code = int(health.get("status_code") or 0)
            network_error = str(health.get("network_error") or "")
            ssl_error = str(health.get("ssl_error") or "")
            redirect_chain = health.get("redirect_chain") if isinstance(health.get("redirect_chain"), list) else []
            final_url = str(health.get("final_url") or source_url)
            source_domain = urlparse(source_url).netloc.lower()
            final_domain = urlparse(final_url).netloc.lower()
            hop_count = _redirect_hop_count(redirect_chain)
            trigger = False
            evidence: dict[str, Any] = {
                "ad_id": ad.get("id"),
                "url_field": field,
                "checked_url": source_url,
                "display_url_full": source_url,
                "final_url": final_url,
            }
            if sitelink_id:
                evidence["sitelink_id"] = sitelink_id
            if "https_available" in health and health.get("https_available") is not None:
                evidence["https_available"] = bool(health.get("https_available"))

            if code == "FINAL_URL_HTTP_ERROR":
                trigger = 400 <= status_code <= 599
                evidence["status_code"] = status_code
            elif code == "FINAL_URL_DNS_TIMEOUT_CONNECTION_ERROR":
                trigger = bool(network_error)
                evidence["network_error"] = network_error
            elif code == "FINAL_URL_SSL_TLS_ERROR":
                trigger = bool(ssl_error)
                evidence["ssl_error"] = ssl_error
            elif code == "REDIRECT_LOOP":
                trigger = len(redirect_chain) != len(set(redirect_chain))
                flow_ru = _redirect_chain_flow_ru(redirect_chain)
                if flow_ru:
                    evidence["redirect_chain_flow_ru"] = flow_ru
                evidence["redirect_chain"] = redirect_chain
            elif code == "REDIRECT_CHAIN_TOO_LONG":
                trigger = hop_count > max_hops
                evidence["redirect_hops"] = hop_count
                evidence["max_redirect_hops"] = max_hops
                flow_ru = _redirect_chain_flow_ru(redirect_chain)
                if flow_ru:
                    evidence["redirect_chain_flow_ru"] = flow_ru
                evidence["redirect_chain"] = redirect_chain
            elif code == "FINAL_DOMAIN_DIFFERS_AFTER_REDIRECT":
                trigger = bool(source_domain and final_domain and source_domain != final_domain)
                evidence["source_domain"] = source_domain
                evidence["final_domain"] = final_domain
                flow_ru = _redirect_chain_flow_ru(redirect_chain)
                if flow_ru:
                    evidence["redirect_chain_flow_ru"] = flow_ru
                if redirect_chain:
                    evidence["redirect_chain"] = redirect_chain
                if source_url and final_url:
                    evidence["domain_shift_ru"] = (
                        f"Исходная ссылка ведёт на хост «{source_domain}», после редиректов финальный URL — «{final_url}» "
                        f"(хост «{final_domain}»)."
                    )
            elif code == "HTTP_USED_INSTEAD_OF_HTTPS":
                trigger = source_url.startswith("http://") or final_url.startswith("http://")

            if not trigger:
                continue
            suffix = "main"
            if sitelink_id:
                suffix = f"sl_{sitelink_id}"
            out.append(
                _base_finding(
                    ad,
                    entity_key=f"ad:{ad.get('id')}:{code.lower()}:{suffix}",
                    issue_location=f"ad:{ad.get('id')}",
                    evidence=evidence,
                    recommendation=rule.get("recommendation_ru", "Исправить ссылку."),
                    impact="Проблемы URL/редиректов/SSL ведут к потере трафика и конверсий.",
                )
            )
    return out


def build_l3_rule_registry() -> dict[str, L3RuleHandler]:
    return {
        "INVALID_URL_SYNTAX": _invalid_url_syntax,
        "MISSING_REQUIRED_UTM": _missing_required_utm,
        "INVALID_UTM": _invalid_utm,
        "INCONSISTENT_UTM_PATTERN": _inconsistent_utm_pattern,
        "MAIN_AND_SITELINK_DOMAINS_MISMATCH": _main_and_sitelink_domains_mismatch,
        "EMPTY_OR_TECHNICAL_URL_PARAMS": _empty_or_technical_url_params,
        "UNRESOLVED_PLACEHOLDER_IN_URL": _unresolved_placeholder_in_url,
        "FINAL_URL_HTTP_ERROR": _http_ssl_redirect_based_checks,
        "FINAL_URL_DNS_TIMEOUT_CONNECTION_ERROR": _http_ssl_redirect_based_checks,
        "FINAL_URL_SSL_TLS_ERROR": _http_ssl_redirect_based_checks,
        "REDIRECT_LOOP": _http_ssl_redirect_based_checks,
        "REDIRECT_CHAIN_TOO_LONG": _http_ssl_redirect_based_checks,
        "FINAL_DOMAIN_DIFFERS_AFTER_REDIRECT": _http_ssl_redirect_based_checks,
        "HTTP_USED_INSTEAD_OF_HTTPS": _http_ssl_redirect_based_checks,
        "BROKEN_SITELINK_URL": _http_ssl_redirect_based_checks,
    }
