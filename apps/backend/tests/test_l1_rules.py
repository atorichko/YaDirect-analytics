from app.services.l1_rules import L1Context, build_l1_rule_registry
from tests.fixture_loader import l1_extensions_from_fixture, load_fixture_dict


def test_active_campaign_respects_yandex_accepted_groups() -> None:
    """Direct API returns AdGroup.Status=ACCEPTED for servable groups (not 'active')."""
    rule = build_l1_rule_registry()["ACTIVE_CAMPAIGN_WITHOUT_ACTIVE_GROUPS"]
    ctx = L1Context(
        account_id="acc1",
        campaigns=[{"id": "100500", "name": "Test", "status": "ON"}],
        groups=[{"id": "g1", "campaign_id": "100500", "name": "G1", "status": "ACCEPTED"}],
        ads=[],
        keywords=[],
        extensions=[],
    )
    assert rule(ctx, {}) == []


def test_active_group_without_active_ads_rule() -> None:
    registry = build_l1_rule_registry()
    rule = registry["ACTIVE_GROUP_WITHOUT_ACTIVE_ADS"]
    ctx = L1Context(
        account_id="acc1",
        campaigns=[{"id": "c1", "status": "active"}],
        groups=[{"id": "g1", "campaign_id": "c1", "status": "active"}],
        ads=[{"id": "a1", "ad_group_id": "g1", "campaign_id": "c1", "status": "paused"}],
        keywords=[],
        extensions=[],
    )
    findings = rule(ctx, {"recommendation_ru": "fix"})
    assert len(findings) == 1
    assert findings[0].group_external_id == "g1"

def test_active_group_without_active_ads_respects_serving_status() -> None:
    registry = build_l1_rule_registry()
    rule = registry["ACTIVE_GROUP_WITHOUT_ACTIVE_ADS"]
    ctx = L1Context(
        account_id="acc1",
        campaigns=[{"id": "c1", "status": "active"}],
        groups=[{"id": "g1", "campaign_id": "c1", "status": "active"}],
        ads=[
            {
                "id": "a1",
                "ad_group_id": "g1",
                "campaign_id": "c1",
                "status": "active",
                "serving_status": "not_eligible",
                "moderation_status": "rejected",
            }
        ],
        keywords=[],
        extensions=[],
    )
    findings = rule(ctx, {"recommendation_ru": "fix"})
    assert len(findings) == 1
    assert findings[0].group_external_id == "g1"


def test_active_ad_rejected_or_restricted_includes_not_eligible_moderation() -> None:
    registry = build_l1_rule_registry()
    rule = registry["ACTIVE_AD_REJECTED_OR_RESTRICTED"]
    ctx = L1Context(
        account_id="acc1",
        campaigns=[{"id": "c1", "status": "active"}],
        groups=[{"id": "g1", "campaign_id": "c1", "status": "active"}],
        ads=[
            {
                "id": "a1",
                "ad_group_id": "g1",
                "campaign_id": "c1",
                "status": "active",
                "title": "Title",
                "serving_status": "not_eligible",
                "moderation_status": "rejected",
            }
        ],
        keywords=[],
        extensions=[],
    )
    findings = rule(ctx, {"recommendation_ru": "fix"})
    assert len(findings) == 1
    assert findings[0].ad_external_id == "a1"


def test_duplicate_keywords_in_group_rule() -> None:
    registry = build_l1_rule_registry()
    rule = registry["DUPLICATE_KEYWORDS_IN_GROUP"]
    ctx = L1Context(
        account_id="acc1",
        campaigns=[],
        groups=[],
        ads=[],
        keywords=[
            {"id": "k1", "ad_group_id": "g1", "campaign_id": "c1", "phrase": "Купить квартиру"},
            {"id": "k2", "ad_group_id": "g1", "campaign_id": "c1", "phrase": "купить   квартиру!!"},
        ],
        extensions=[],
    )
    findings = rule(ctx, {"recommendation_ru": "fix"})
    assert len(findings) == 1
    assert findings[0].evidence["normalized_keyword"] == "купить квартиру"


def test_expired_date_in_extensions_yandex_fixture_sitelink() -> None:
    data = load_fixture_dict()
    extensions = l1_extensions_from_fixture(data)
    rule = build_l1_rule_registry()["EXPIRED_DATE_IN_EXTENSIONS"]
    ctx = L1Context(
        account_id="fixture",
        campaigns=[],
        groups=[],
        ads=[],
        keywords=[],
        extensions=extensions,
    )
    findings = rule(ctx, {})
    ad_ids = {str(f.evidence.get("ad_id")) for f in findings}
    assert "A20031" in ad_ids
    assert any(str(f.evidence.get("expired_date")) == "31.12.2025" for f in findings)


def test_campaign_geo_overlaps_campaign_negatives_rule() -> None:
    rule = build_l1_rule_registry()["CAMPAIGN_GEO_OVERLAPS_CAMPAIGN_NEGATIVES"]
    ctx = L1Context(
        account_id="acc1",
        campaigns=[
            {
                "id": "c1",
                "status": "active",
                "name": "Test",
                "geo": ["Москва и область"],
                "negative_keywords": ["москва"],
            }
        ],
        groups=[],
        ads=[],
        keywords=[],
        extensions=[],
    )
    findings = rule(ctx, {})
    assert len(findings) == 1
    assert "москва" in findings[0].evidence["overlap_tokens"]

    paused = L1Context(
        account_id="acc1",
        campaigns=[
            {
                "id": "c2",
                "status": "paused",
                "geo": ["Москва"],
                "negative_keywords": ["москва"],
            }
        ],
        groups=[],
        ads=[],
        keywords=[],
        extensions=[],
    )
    assert rule(paused, {}) == []


def test_active_group_without_targeting_respects_autotargeting() -> None:
    rule = build_l1_rule_registry()["ACTIVE_GROUP_WITHOUT_TARGETING"]
    base_group = {
        "id": "g1",
        "campaign_id": "c1",
        "status": "active",
        "name": "G",
        "autotargeting": "disabled",
        "audiences": [],
    }
    ctx_flag = L1Context(
        account_id="a",
        campaigns=[{"id": "c1", "status": "active"}],
        groups=[base_group],
        ads=[],
        keywords=[],
        extensions=[],
    )
    assert len(rule(ctx_flag, {})) == 1

    ctx_auto = L1Context(
        account_id="a",
        campaigns=[{"id": "c1", "status": "active"}],
        groups=[{**base_group, "autotargeting": "enabled"}],
        ads=[],
        keywords=[],
        extensions=[],
    )
    assert rule(ctx_auto, {}) == []


def test_campaign_self_competition_uses_account_keyword_scope() -> None:
    rule = build_l1_rule_registry()["CAMPAIGN_SELF_COMPETITION_BY_GEO_AND_SEMANTICS"]
    ctx = L1Context(
        account_id="acc",
        campaigns=[{"id": "C200", "status": "active", "geo": ["Москва"]}],
        groups=[],
        ads=[],
        keywords=[
            {
                "id": "k1",
                "campaign_id": "C200",
                "ad_group_id": "g1",
                "text": "купить квартиру москва",
                "status": "active",
            },
        ],
        extensions=[],
        account_campaigns=[
            {"id": "C200", "status": "active", "geo": ["Москва"]},
            {"id": "C300", "status": "active", "geo": ["Москва"]},
        ],
        account_keywords=[
            {
                "id": "k1",
                "campaign_id": "C200",
                "ad_group_id": "g1",
                "text": "купить квартиру москва",
                "status": "active",
            },
            {
                "id": "k2",
                "campaign_id": "C300",
                "ad_group_id": "g2",
                "text": "купить квартиру москва",
                "status": "active",
            },
        ],
        scoped_campaign_external_id="C200",
    )
    findings = rule(ctx, {})
    assert len(findings) == 1
    assert findings[0].campaign_external_id == "C200"
    assert {findings[0].evidence["left_campaign_id"], findings[0].evidence["right_campaign_id"]} == {"C200", "C300"}


def test_duplicate_ads_detects_not_eligible_pairs() -> None:
    rule = build_l1_rule_registry()["DUPLICATE_ADS"]
    ctx = L1Context(
        account_id="a",
        campaigns=[],
        groups=[],
        keywords=[],
        extensions=[],
        ads=[
            {
                "id": "a1",
                "ad_group_id": "G2001",
                "campaign_id": "C200",
                "status": "active",
                "serving_status": "not_eligible",
                "title": "Same",
                "text": "Same text",
                "url": "https://x.com",
            },
            {
                "id": "a2",
                "ad_group_id": "G2001",
                "campaign_id": "C200",
                "status": "active",
                "serving_status": "not_eligible",
                "title": "Same",
                "text": "Same text",
                "url": "https://x.com",
            },
        ],
    )
    findings = rule(ctx, {})
    assert len(findings) == 1
    assert set(findings[0].evidence["ad_ids"]) == {"a1", "a2"}
