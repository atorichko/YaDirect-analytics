from app.services.l1_rules import L1Context, build_l1_rule_registry
from tests.fixture_loader import l1_extensions_from_fixture, load_fixture_dict


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
