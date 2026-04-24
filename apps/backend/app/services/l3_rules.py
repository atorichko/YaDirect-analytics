from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib.parse import parse_qsl, urlparse

from app.services.l1_rules import FindingDraft

_TECH_VALUES = {"", "undefined", "null", "none", "(not set)"}
_PLACEHOLDER_RE = re.compile(r"(\{\{[^{}]+\}\}|\{[^{}]+\}|%[^%]+%|\[[^\[\]]+\]|<[^<>]+>)")
# utm_content / utm_term often differ on purpose (объявление vs быстрые ссылки).
_STRICT_UTM_KEYS = frozenset({"utm_source", "utm_medium", "utm_campaign"})


@dataclass(slots=True)
class L3Context:
    account_id: str
    ads: list[dict[str, Any]]
    extensions: list[dict[str, Any]]


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
        if str(v).strip().lower() in _TECH_VALUES:
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
                "validation_error": "invalid_syntax",
                "url_syntax_issues": issues,
                "url_value_segments": parts,
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
            params = {k.lower(): v for k, v in parse_qsl(parsed.query, keep_blank_values=True)}
            missing = [param for param in required if param.lower() not in params]
            if not missing:
                continue
            ek = f"ad:{ad.get('id')}:{field}:missing_utm"
            if sitelink_id:
                ek = f"ad:{ad.get('id')}:sl:{sitelink_id}:missing_utm"
            ev: dict[str, Any] = {
                "ad_id": ad.get("id"),
                "url_field": field,
                "checked_url": value,
                "missing_utm_params": missing,
                "utm_param_status": [
                    {"param": p, "present": p.lower() in params, "value": params.get(p.lower())} for p in required
                ],
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
            err_codes = _utm_error_codes(raw_q, raw_pairs)
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
                "utm_validation_errors": err_codes,
                "utm_issue_details": details,
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
                    "main_domain": main_domain,
                    "sitelink_urls": rows,
                    "sitelink_domains": sorted(set(mismatch_domains)),
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
                "invalid_params": sorted(bad.keys()),
                "empty_or_technical_values": bad,
                "query_highlight_segments": segments,
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
            matched = _PLACEHOLDER_RE.findall(value)
            if not matched:
                continue
            ek = f"ad:{ad.get('id')}:{field}:placeholder"
            if sitelink_id:
                ek = f"ad:{ad.get('id')}:sl:{sitelink_id}:placeholder"
            ev: dict[str, Any] = {
                "ad_id": ad.get("id"),
                "url_field": field,
                "checked_url": value,
                "matched_placeholder": matched[0] if len(matched) == 1 else matched,
                "matched_placeholders": matched,
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


def _inconsistent_utm_pattern(ctx: L3Context, rule: dict[str, Any]) -> list[FindingDraft]:
    """Flag when utm_source / utm_medium / utm_campaign differ across URLs of the same ad."""
    out: list[FindingDraft] = []
    for ad in ctx.ads:
        by_key: dict[str, set[str]] = {k: set() for k in _STRICT_UTM_KEYS}
        for _field, value, _sid in _collect_ad_urls(ad):
            parsed = urlparse(value)
            for k, v in parse_qsl(parsed.query, keep_blank_values=True):
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
                evidence={"ad_id": ad.get("id"), "utm_conflicts": conflicts},
                recommendation=rule.get(
                    "recommendation_ru",
                    "Унифицировать UTM-разметку между основной ссылкой и быстрыми ссылками.",
                ),
                impact="Разная UTM-разметка внутри одного объявления ломает сопоставление данных в аналитике.",
            )
        )
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
            out.append(
                _base_finding(
                    ad,
                    entity_key=f"ad:{ad.get('id')}:{code.lower()}",
                    issue_location=f"ad:{ad.get('id')}",
                    evidence={
                        "ad_id": ad.get("id"),
                        "broken_sitelinks": ids,
                        "broken_sitelink_urls": [
                            {"sitelink_id": str(x.get("sitelink_id")), "url": x.get("url")} for x in broken if isinstance(x, dict)
                        ],
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
                evidence["redirect_chain"] = redirect_chain
            elif code == "REDIRECT_CHAIN_TOO_LONG":
                trigger = hop_count > max_hops
                evidence["redirect_hops"] = hop_count
                evidence["redirect_chain"] = redirect_chain
                evidence["max_redirect_hops"] = max_hops
            elif code == "FINAL_DOMAIN_DIFFERS_AFTER_REDIRECT":
                trigger = bool(source_domain and final_domain and source_domain != final_domain)
                evidence["source_domain"] = source_domain
                evidence["final_domain"] = final_domain
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
