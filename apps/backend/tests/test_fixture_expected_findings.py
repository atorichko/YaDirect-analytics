"""Сверка детерминированных находок с эталоном из tests/fixtures/expected_findings.json."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.l1_rules import FindingDraft, L1Context, build_l1_rule_registry
from app.services.l2_rules import L2Context, build_l2_rule_registry
from app.services.l3_rules import L3Context, build_l3_rule_registry
from tests.fixture_loader import (
    ad_groups_normalized_from_fixture,
    campaigns_normalized_from_fixture,
    l1_extensions_from_fixture,
    load_fixture_dict,
    metrika_goals_from_fixture,
)


def _normalize_health(item: dict[str, Any]) -> dict[str, Any]:
    ssl = item.get("ssl_check") or {}
    return {
        "status_code": item.get("status_code"),
        "network_error": item.get("network_error"),
        "ssl_error": ssl.get("error") if isinstance(ssl, dict) else None,
        "redirect_chain": item.get("redirect_chain") or [],
        "final_url": item.get("final_url"),
        "https_available": item.get("https_available"),
    }


def _is_active_state(value: object) -> bool:
    return str(value or "").lower() in {"active", "on", "enabled"}


def _fixture_ads_with_health(data: dict[str, Any]) -> list[dict[str, Any]]:
    checks_raw = data.get("technical_checks") or []
    check_map = {
        str(x.get("checked_url")): _normalize_health(x)
        for x in checks_raw
        if isinstance(x, dict) and x.get("checked_url")
    }
    out: list[dict[str, Any]] = []
    for c in data.get("campaigns", []) or []:
        campaign_id = str(c.get("campaign_id") or "")
        for g in c.get("groups", []) or []:
            group_id = str(g.get("group_id") or "")
            if not _is_active_state(g.get("status")):
                continue
            for ad in g.get("ads", []) or []:
                if not _is_active_state(ad.get("status")):
                    continue
                ad_id = str(ad.get("ad_id") or "")
                if not ad_id:
                    continue
                enriched_sitelinks: list[dict[str, Any]] = []
                for sl in ad.get("sitelinks") or []:
                    if not isinstance(sl, dict):
                        continue
                    surl = str(sl.get("url") or "")
                    sh = check_map.get(surl) or {}
                    sl2 = dict(sl)
                    sl2["url_health_error"] = bool(
                        sh.get("network_error")
                        or sh.get("ssl_error")
                        or (isinstance(sh.get("status_code"), int) and int(sh.get("status_code") or 0) >= 400)
                    )
                    sl2["url_health"] = sh
                    enriched_sitelinks.append(sl2)
                main_url = str(ad.get("url") or "")
                out.append(
                    {
                        "id": ad_id,
                        "campaign_id": campaign_id,
                        "ad_group_id": group_id,
                        "status": ad.get("status"),
                        "state": ad.get("status"),
                        "serving_status": ad.get("serving_status"),
                        "moderation_status": ad.get("moderation_status"),
                        "moderation_notes": ad.get("moderation_notes"),
                        "type": "TEXT_AD",
                        "title": ad.get("title"),
                        "text": ad.get("text"),
                        "url": main_url,
                        "final_url": main_url,
                        "sitelinks": enriched_sitelinks,
                        "callouts": ad.get("callouts") or [],
                        "display_url": ad.get("display_url"),
                        "contact_info": ad.get("contact_info"),
                        "image": ad.get("image"),
                        "url_health": check_map.get(main_url) or {},
                    }
                )
    return out


def _build_l1_context(data: dict[str, Any]) -> L1Context:
    campaigns = campaigns_normalized_from_fixture(data)
    groups: list[dict[str, Any]] = []
    keywords: list[dict[str, Any]] = []
    ads: list[dict[str, Any]] = []
    for c in data.get("campaigns", []) or []:
        cid = str(c.get("campaign_id") or "")
        for g in c.get("groups", []) or []:
            gid = str(g.get("group_id") or "")
            groups.append(
                {
                    "id": gid,
                    "campaign_id": cid,
                    "name": g.get("group_name"),
                    "status": g.get("status"),
                    "negative_keywords": g.get("negative_keywords") or [],
                    "autotargeting": g.get("autotargeting"),
                    "audiences": g.get("audiences") or [],
                    "region_ids": g.get("region_ids") or [],
                }
            )
            for kw in g.get("keywords", []) or []:
                phrase = kw.get("text")
                keywords.append(
                    {
                        "id": str(kw.get("keyword_id")),
                        "campaign_id": cid,
                        "ad_group_id": gid,
                        "text": phrase,
                        "phrase": phrase,
                        "status": kw.get("status"),
                        "state": kw.get("status"),
                    }
                )
            for ad in g.get("ads", []) or []:
                aid = str(ad.get("ad_id") or "")
                if not aid:
                    continue
                ads.append(
                    {
                        "id": aid,
                        "campaign_id": cid,
                        "ad_group_id": gid,
                        "status": ad.get("status"),
                        "state": ad.get("status"),
                        "serving_status": ad.get("serving_status"),
                        "moderation_status": ad.get("moderation_status"),
                        "title": ad.get("title"),
                        "text": ad.get("text"),
                        "url": ad.get("url"),
                        "final_url": ad.get("url"),
                        "sitelinks": ad.get("sitelinks") or [],
                        "callouts": ad.get("callouts") or [],
                        "display_url": ad.get("display_url"),
                        "contact_info": ad.get("contact_info"),
                        "image": ad.get("image"),
                    }
                )
    extensions = l1_extensions_from_fixture(data)
    return L1Context(
        account_id=str(data.get("account", {}).get("account_id") or "acc_001"),
        campaigns=campaigns,
        groups=groups,
        ads=ads,
        keywords=keywords,
        extensions=extensions,
    )


def _list_subset(actual: Any, expected: list[Any]) -> bool:
    if not isinstance(actual, list):
        return False
    if all(isinstance(x, (str, int, float, bool)) or x is None for x in expected):
        return set(expected).issubset(set(actual))
    return False


def _evidence_contains(actual: dict[str, Any], needle: dict[str, Any]) -> bool:
    for k, ev in needle.items():
        if k not in actual:
            return False
        av = actual[k]
        if isinstance(ev, dict):
            if not isinstance(av, dict) or not _evidence_contains(av, ev):
                return False
        elif isinstance(ev, list):
            if not _list_subset(av, ev):
                return False
        elif av != ev:
            return False
    return True


def _refs_match(draft: FindingDraft, refs: dict[str, Any]) -> bool:
    if refs.get("campaign_id") and str(refs["campaign_id"]) != str(draft.campaign_external_id or ""):
        return False
    if refs.get("group_id") and str(refs["group_id"]) != str(draft.group_external_id or ""):
        return False
    ad_ref = refs.get("ad_id")
    if ad_ref is not None:
        ad_got = str(draft.ad_external_id or draft.evidence.get("ad_id") or "")
        if str(ad_ref) != ad_got:
            return False
    if refs.get("keyword_id") is not None:
        if str(draft.evidence.get("keyword_id") or "") != str(refs["keyword_id"]):
            return False
    if refs.get("sitelink_id") is not None:
        if str(draft.evidence.get("sitelink_id") or "") != str(refs["sitelink_id"]):
            return False
    if refs.get("url_field") is not None:
        exp_uf = str(refs["url_field"])
        got_uf = str(draft.evidence.get("url_field") or "")
        if exp_uf == "ad.sitelinks[].url":
            if not (got_uf.startswith("ad.sitelinks[") and got_uf.endswith("].url")):
                return False
        elif got_uf != exp_uf:
            return False
    if refs.get("keyword_ids") is not None:
        exp = sorted(str(x) for x in refs["keyword_ids"])
        got = sorted(str(x) for x in (draft.evidence.get("keyword_ids") or []))
        if exp != got:
            return False
    if refs.get("ad_ids") is not None:
        exp = sorted(str(x) for x in refs["ad_ids"])
        got = sorted(str(x) for x in (draft.evidence.get("ad_ids") or []))
        if exp != got:
            return False
    return True


def _collect_tagged_findings(data: dict[str, Any]) -> list[tuple[str, FindingDraft]]:
    policy = data.get("policy") or {}
    l1_ctx = _build_l1_context(data)
    l1_cfg: dict[str, Any] = {
        "required_extensions": policy.get("required_extensions"),
        "min_conversions_for_learning": int(policy.get("min_conversions_for_learning") or 10),
        "budget_limited_days_threshold": 3,
        "recommendation_ru": "x",
    }
    out: list[tuple[str, FindingDraft]] = []
    reg1 = build_l1_rule_registry()
    for code, fn in reg1.items():
        for d in fn(l1_ctx, dict(l1_cfg)):
            out.append((code, d))

    l2_ctx = L2Context(
        account_id=str(data.get("account", {}).get("account_id") or "acc_001"),
        campaigns=campaigns_normalized_from_fixture(data),
        metrika_goals=metrika_goals_from_fixture(data),
    )
    reg2 = build_l2_rule_registry()
    l2_raw = {
        "recommendation_ru": "x",
        "min_conversions_for_learning": int(policy.get("min_conversions_for_learning") or 10),
        "budget_limited_days_threshold": 3,
    }
    for code, fn in reg2.items():
        for d in fn(l2_ctx, l2_raw):
            out.append((code, d))

    l3_ctx = L3Context(
        account_id=str(data.get("account", {}).get("account_id") or "acc_001"),
        ads=_fixture_ads_with_health(data),
        extensions=[],
        campaigns=campaigns_normalized_from_fixture(data),
        groups=ad_groups_normalized_from_fixture(data),
    )
    reg3 = build_l3_rule_registry()
    for code, fn in reg3.items():
        l3_raw = {
            "rule_code": code,
            "recommendation_ru": "x",
            "required_utm_params": policy.get("required_utm_params")
            or ["utm_source", "utm_medium", "utm_campaign", "utm_content"],
            "max_redirect_hops": int(policy.get("max_redirect_hops") or 5),
        }
        for d in fn(l3_ctx, l3_raw):
            out.append((code, d))
    return out


def test_fixture_matches_expected_deterministic_findings() -> None:
    data = load_fixture_dict()
    path = Path(__file__).resolve().parent / "fixtures" / "expected_findings.json"
    spec = json.loads(path.read_text(encoding="utf-8"))
    tagged = _collect_tagged_findings(data)
    missing: list[str] = []
    for exp in spec.get("exact_findings", []) or []:
        rule_code = str(exp.get("rule_code") or "")
        refs = exp.get("refs") or {}
        needle = exp.get("evidence_contains") or {}
        hit = next(
            (
                d
                for rc, d in tagged
                if rc == rule_code and _refs_match(d, refs) and _evidence_contains(d.evidence, needle)
            ),
            None,
        )
        if hit is None:
            missing.append(str(exp.get("finding_key") or rule_code))
    assert not missing, "No matching draft for expected findings:\n" + "\n".join(missing)
