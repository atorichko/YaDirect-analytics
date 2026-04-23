from app.services.l3_rules import L3Context, build_l3_rule_registry


def test_invalid_url_syntax_rule() -> None:
    rule = build_l3_rule_registry()["INVALID_URL_SYNTAX"]
    ctx = L3Context(
        account_id="acc1",
        ads=[{"id": "a1", "campaign_id": "c1", "ad_group_id": "g1", "url": "not-a-url"}],
        extensions=[],
    )
    findings = rule(ctx, {"recommendation_ru": "fix"})
    assert len(findings) == 1
    assert findings[0].evidence["validation_error"] == "invalid_syntax"


def test_missing_required_utm_rule() -> None:
    rule = build_l3_rule_registry()["MISSING_REQUIRED_UTM"]
    ctx = L3Context(
        account_id="acc1",
        ads=[{"id": "a1", "campaign_id": "c1", "ad_group_id": "g1", "url": "https://example.com/?utm_source=yandex"}],
        extensions=[],
    )
    findings = rule(ctx, {"required_utm_params": ["utm_source", "utm_medium", "utm_campaign"]})
    assert len(findings) == 1
    assert "utm_medium" in findings[0].evidence["missing_utm_params"]


def test_main_and_sitelink_domains_mismatch_rule() -> None:
    rule = build_l3_rule_registry()["MAIN_AND_SITELINK_DOMAINS_MISMATCH"]
    ctx = L3Context(
        account_id="acc1",
        ads=[
            {
                "id": "a1",
                "campaign_id": "c1",
                "ad_group_id": "g1",
                "url": "https://example.com/main",
                "sitelinks": [{"url": "https://another.com/page"}],
            }
        ],
        extensions=[],
    )
    findings = rule(ctx, {})
    assert len(findings) == 1
    assert findings[0].evidence["main_domain"] == "example.com"


def test_inconsistent_utm_pattern_rule() -> None:
    rule = build_l3_rule_registry()["INCONSISTENT_UTM_PATTERN"]
    ctx = L3Context(
        account_id="acc1",
        ads=[
            {
                "id": "a1",
                "campaign_id": "c1",
                "ad_group_id": "g1",
                "url": "https://example.com/?utm_source=yandex&utm_medium=cpc&utm_campaign=cmp_a",
                "sitelinks": [
                    {"url": "https://example.com/x?utm_source=yandex&utm_medium=cpc&utm_campaign=cmp_b"},
                ],
            }
        ],
        extensions=[],
    )
    findings = rule(ctx, {})
    assert len(findings) == 1
    conflicts = findings[0].evidence.get("utm_conflicts") or {}
    assert "utm_campaign" in conflicts
    assert "cmp_a" in conflicts["utm_campaign"] and "cmp_b" in conflicts["utm_campaign"]
