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


def _collect_ad_urls(ad: dict[str, Any]) -> list[tuple[str, str]]:
    urls: list[tuple[str, str]] = []
    main_url = ad.get("url") or ad.get("final_url")
    if isinstance(main_url, str) and main_url.strip():
        urls.append(("ad.url", main_url.strip()))
    sitelinks = ad.get("sitelinks") or []
    if isinstance(sitelinks, list):
        for idx, item in enumerate(sitelinks):
            if isinstance(item, dict):
                url = item.get("url")
                if isinstance(url, str) and url.strip():
                    urls.append((f"ad.sitelinks[{idx}].url", url.strip()))
    return urls


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
        for field, value in _collect_ad_urls(ad):
            parsed = urlparse(value)
            if parsed.scheme in {"http", "https"} and parsed.netloc:
                continue
            out.append(
                _base_finding(
                    ad,
                    entity_key=f"ad:{ad.get('id')}:{field}:invalid_url",
                    issue_location=f"ad:{ad.get('id')}",
                    evidence={"ad_id": ad.get("id"), "url_field": field, "url_value": value, "validation_error": "invalid_syntax"},
                    recommendation=rule.get("recommendation_ru", "Исправить формат URL."),
                    impact="Некорректный URL ломает переходы и трафик.",
                )
            )
    return out


def _missing_required_utm(ctx: L3Context, rule: dict[str, Any]) -> list[FindingDraft]:
    required = [str(x) for x in rule.get("required_utm_params", []) if str(x)]
    out: list[FindingDraft] = []
    for ad in ctx.ads:
        for field, value in _collect_ad_urls(ad):
            parsed = urlparse(value)
            params = {k.lower(): v for k, v in parse_qsl(parsed.query, keep_blank_values=True)}
            missing = [param for param in required if param.lower() not in params]
            if not missing:
                continue
            out.append(
                _base_finding(
                    ad,
                    entity_key=f"ad:{ad.get('id')}:{field}:missing_utm",
                    issue_location=f"ad:{ad.get('id')}",
                    evidence={"ad_id": ad.get("id"), "url_field": field, "missing_utm_params": missing},
                    recommendation=rule.get("recommendation_ru", "Добавить обязательные UTM-параметры."),
                    impact="Без обязательных UTM нарушается сквозная аналитика и атрибуция.",
                )
            )
    return out


def _invalid_utm(ctx: L3Context, rule: dict[str, Any]) -> list[FindingDraft]:
    out: list[FindingDraft] = []
    for ad in ctx.ads:
        for field, value in _collect_ad_urls(ad):
            parsed = urlparse(value)
            raw_pairs = parse_qsl(parsed.query, keep_blank_values=True)
            duplicates = {k for k, _ in raw_pairs if sum(1 for key, _ in raw_pairs if key == k) > 1}
            invalid_values = [k for k, v in raw_pairs if str(v).strip().lower() in _TECH_VALUES]
            if not duplicates and not invalid_values:
                continue
            out.append(
                _base_finding(
                    ad,
                    entity_key=f"ad:{ad.get('id')}:{field}:invalid_utm",
                    issue_location=f"ad:{ad.get('id')}",
                    evidence={
                        "ad_id": ad.get("id"),
                        "url_field": field,
                        "utm_validation_errors": {
                            "duplicate_params": sorted(duplicates),
                            "invalid_values": invalid_values,
                        },
                    },
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
        sitelink_domains = []
        for item in sitelinks:
            if isinstance(item, dict) and isinstance(item.get("url"), str):
                sitelink_domains.append(urlparse(item["url"]).netloc.lower())
        mismatch = [domain for domain in sitelink_domains if domain and domain != main_domain]
        if not mismatch:
            continue
        out.append(
            _base_finding(
                ad,
                entity_key=f"ad:{ad.get('id')}:domain_mismatch",
                issue_location=f"ad:{ad.get('id')}",
                evidence={
                    "ad_id": ad.get("id"),
                    "main_domain": main_domain,
                    "sitelink_domains": sorted(set(sitelink_domains)),
                },
                recommendation=rule.get("recommendation_ru", "Привести все ссылки объявления к согласованному домену."),
                impact="Разные домены в объявлении и быстрых ссылках ухудшают консистентность лендинга.",
            )
        )
    return out


def _empty_or_technical_url_params(ctx: L3Context, rule: dict[str, Any]) -> list[FindingDraft]:
    out: list[FindingDraft] = []
    for ad in ctx.ads:
        for field, value in _collect_ad_urls(ad):
            parsed = urlparse(value)
            pairs = parse_qsl(parsed.query, keep_blank_values=True)
            invalid = [k for k, v in pairs if str(v).strip().lower() in _TECH_VALUES]
            if not invalid:
                continue
            out.append(
                _base_finding(
                    ad,
                    entity_key=f"ad:{ad.get('id')}:{field}:technical_params",
                    issue_location=f"ad:{ad.get('id')}",
                    evidence={"ad_id": ad.get("id"), "url_field": field, "invalid_params": invalid},
                    recommendation=rule.get("recommendation_ru", "Удалить пустые или технические параметры из ссылки."),
                    impact="Технические параметры в URL ухудшают качество трекинга и могут ломать маршрутизацию.",
                )
            )
    return out


def _unresolved_placeholder_in_url(ctx: L3Context, rule: dict[str, Any]) -> list[FindingDraft]:
    out: list[FindingDraft] = []
    for ad in ctx.ads:
        for field, value in _collect_ad_urls(ad):
            matched = _PLACEHOLDER_RE.findall(value)
            if not matched:
                continue
            out.append(
                _base_finding(
                    ad,
                    entity_key=f"ad:{ad.get('id')}:{field}:placeholder",
                    issue_location=f"ad:{ad.get('id')}",
                    evidence={"ad_id": ad.get("id"), "url_field": field, "matched_placeholder": matched},
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
        for _field, value in _collect_ad_urls(ad):
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
    for ad in ctx.ads:
        health = ad.get("url_health") or {}
        status_code = int(health.get("status_code") or 0)
        network_error = str(health.get("network_error") or "")
        ssl_error = str(health.get("ssl_error") or "")
        redirect_chain = health.get("redirect_chain") if isinstance(health.get("redirect_chain"), list) else []
        final_url = str(health.get("final_url") or ad.get("url") or "")
        source_url = str(ad.get("url") or "")
        source_domain = urlparse(source_url).netloc.lower()
        final_domain = urlparse(final_url).netloc.lower()
        trigger = False
        evidence: dict[str, Any] = {"ad_id": ad.get("id"), "checked_url": source_url, "final_url": final_url}

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
            trigger = len(redirect_chain) > max_hops
            evidence["redirect_hops"] = len(redirect_chain)
            evidence["redirect_chain"] = redirect_chain
            evidence["max_redirect_hops"] = max_hops
        elif code == "FINAL_DOMAIN_DIFFERS_AFTER_REDIRECT":
            trigger = bool(source_domain and final_domain and source_domain != final_domain)
            evidence["source_domain"] = source_domain
            evidence["final_domain"] = final_domain
        elif code == "HTTP_USED_INSTEAD_OF_HTTPS":
            trigger = source_url.startswith("http://") or final_url.startswith("http://")
        elif code == "BROKEN_SITELINK_URL":
            broken = [item for item in (ad.get("sitelinks") or []) if isinstance(item, dict) and item.get("url_health_error")]
            trigger = len(broken) > 0
            evidence["broken_sitelinks"] = broken

        if trigger:
            out.append(
                _base_finding(
                    ad,
                    entity_key=f"ad:{ad.get('id')}:{code.lower()}",
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
