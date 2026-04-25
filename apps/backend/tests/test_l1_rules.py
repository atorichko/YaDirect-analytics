import pytest

from app.services.l1_rules import L1Context, build_l1_rule_registry
from tests.fixture_loader import campaigns_normalized_from_fixture, l1_extensions_from_fixture, load_fixture_dict


_LONG_IPOTEKA_MINUS_TAIL = (
    "ипотека -банк -втб -2026 -выкса -жилье -первоначальный -калькулятор -квартира "
    "-можно -покупка -сбер -сбербанк -сельский -семейный"
)


def _ctx_dup_kw_cross_groups(phrase_left: str, phrase_right: str) -> L1Context:
    return L1Context(
        account_id="a",
        campaigns=[{"id": "c1", "status": "active"}],
        groups=[
            {"id": "g1", "campaign_id": "c1", "status": "active"},
            {"id": "g2", "campaign_id": "c1", "status": "active"},
        ],
        ads=[],
        keywords=[
            {
                "id": "k1",
                "campaign_id": "c1",
                "ad_group_id": "g1",
                "phrase": phrase_left,
                "text": phrase_left,
                "state": "on",
            },
            {
                "id": "k2",
                "campaign_id": "c1",
                "ad_group_id": "g2",
                "phrase": phrase_right,
                "text": phrase_right,
                "state": "on",
            },
        ],
        extensions=[],
    )


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
        groups=[
            {"id": "g1", "campaign_id": "c1", "name": "G", "negative_keywords": ["москва"]},
        ],
        ads=[],
        keywords=[
            {"id": "k1", "ad_group_id": "g1", "campaign_id": "c1", "phrase": "Купить квартиру", "state": "on"},
            {"id": "k2", "ad_group_id": "g1", "campaign_id": "c1", "phrase": "купить   квартиру!!", "state": "on"},
            {"id": "k3", "ad_group_id": "g1", "campaign_id": "c1", "phrase": "квартира москва", "state": "on"},
        ],
        extensions=[],
    )
    findings = rule(ctx, {"recommendation_ru": "fix"})
    assert len(findings) == 1
    assert findings[0].evidence["normalized_keyword"] == "купить квартиру"
    conflicts = findings[0].evidence.get("minus_word_conflicts") or []
    assert any(c.get("keyword_id") == "k3" and "москва" in (c.get("minus_tokens") or []) for c in conflicts)


def test_missing_required_extensions_skips_when_extension_fields_not_loaded() -> None:
    rule = build_l1_rule_registry()["MISSING_REQUIRED_EXTENSIONS"]
    ctx = L1Context(
        account_id="acc1",
        campaigns=[{"id": "c1", "status": "active"}],
        groups=[{"id": "g1", "campaign_id": "c1", "status": "active"}],
        ads=[
            {
                "id": "a1",
                "campaign_id": "c1",
                "ad_group_id": "g1",
                "state": "on",
                "status": "active",
                # no sitelinks/callouts/display_url/contact_info/image keys loaded
            }
        ],
        keywords=[],
        extensions=[],
    )
    findings = rule(ctx, {})
    assert findings == []


def test_missing_required_extensions_uses_extension_snapshot_fallback() -> None:
    rule = build_l1_rule_registry()["MISSING_REQUIRED_EXTENSIONS"]
    ctx = L1Context(
        account_id="acc1",
        campaigns=[{"id": "c1", "status": "active"}],
        groups=[{"id": "g1", "campaign_id": "c1", "status": "active"}],
        ads=[
            {
                "id": "a1",
                "campaign_id": "c1",
                "ad_group_id": "g1",
                "state": "on",
                "status": "active",
            }
        ],
        keywords=[],
        extensions=[
            {
                "ad_id": "a1",
                "campaign_id": "c1",
                "ad_group_id": "g1",
                "sitelinks": [],
                "callouts": ["24/7"],
                "display_url": "example.com",
                "contact_info": {"phone": "+70000000000"},
                "image": {"hash": "abc"},
            }
        ],
    )
    findings = rule(ctx, {})
    assert len(findings) == 1
    assert findings[0].evidence.get("missing_extensions") == ["sitelinks"]


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
    assert any(str(f.evidence.get("matched_date_text")) == "31.12.2025" for f in findings)


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


def test_campaign_self_competition_skipped_when_campaign_name_has_retargeting() -> None:
    rule = build_l1_rule_registry()["CAMPAIGN_SELF_COMPETITION_BY_GEO_AND_SEMANTICS"]
    phrase = "купить квартиру москва"
    ctx = L1Context(
        account_id="acc",
        campaigns=[
            {"id": "C200", "status": "active", "name": "поиск бренд"},
            {"id": "C300", "status": "active", "name": "рся ретаргетинг квиз"},
        ],
        groups=[],
        ads=[],
        keywords=[
            {"id": "k1", "campaign_id": "C200", "ad_group_id": "g1", "text": phrase, "state": "on"},
            {"id": "k2", "campaign_id": "C300", "ad_group_id": "g2", "text": phrase, "state": "on"},
        ],
        extensions=[],
    )
    assert rule(ctx, {}) == []


def test_campaign_self_competition_fires_when_geo_missing_in_snapshot() -> None:
    """Production snapshots may lack geo/RegionIds; do not suppress semantic overlap."""
    rule = build_l1_rule_registry()["CAMPAIGN_SELF_COMPETITION_BY_GEO_AND_SEMANTICS"]
    ctx = L1Context(
        account_id="acc",
        campaigns=[
            {"id": "C200", "status": "active"},
            {"id": "C300", "status": "active"},
        ],
        groups=[],
        ads=[],
        keywords=[
            {
                "id": "k1",
                "campaign_id": "C200",
                "ad_group_id": "g1",
                "text": "купить квартиру москва",
                "state": "on",
            },
            {
                "id": "k2",
                "campaign_id": "C300",
                "ad_group_id": "g2",
                "text": "купить квартиру москва",
                "state": "on",
            },
        ],
        extensions=[],
    )
    findings = rule(ctx, {})
    assert len(findings) == 1
    assert findings[0].evidence.get("geo_overlap") == ["geo:unknown"]


def test_campaign_self_competition_no_finding_when_geo_disjoint_by_region_ids() -> None:
    rule = build_l1_rule_registry()["CAMPAIGN_SELF_COMPETITION_BY_GEO_AND_SEMANTICS"]
    phrase = "купить квартиру"
    ctx = L1Context(
        account_id="acc",
        campaigns=[{"id": "C200", "status": "active"}],
        groups=[],
        ads=[],
        keywords=[
            {
                "id": "k1",
                "campaign_id": "C200",
                "ad_group_id": "g1",
                "text": phrase,
                "status": "active",
            },
        ],
        extensions=[],
        account_campaigns=[
            {"id": "C200", "status": "active"},
            {"id": "C300", "status": "active"},
        ],
        account_keywords=[
            {
                "id": "k1",
                "campaign_id": "C200",
                "ad_group_id": "g1",
                "text": phrase,
                "status": "active",
            },
            {
                "id": "k2",
                "campaign_id": "C300",
                "ad_group_id": "g2",
                "text": phrase,
                "status": "active",
            },
        ],
        account_groups=[
            {"id": "g1", "campaign_id": "C200", "region_ids": [1]},
            {"id": "g2", "campaign_id": "C300", "region_ids": [2]},
        ],
        scoped_campaign_external_id="C200",
    )
    assert rule(ctx, {}) == []


def test_duplicate_keywords_with_overlap_suppressed_by_phrase_minus_stem() -> None:
    rule = build_l1_rule_registry()["DUPLICATE_KEYWORDS_WITH_OVERLAP"]
    ctx = L1Context(
        account_id="a",
        campaigns=[{"id": "c1", "status": "active"}],
        groups=[{"id": "g1", "campaign_id": "c1", "status": "active"}],
        ads=[],
        keywords=[
            {
                "id": "k1",
                "campaign_id": "c1",
                "ad_group_id": "g1",
                "phrase": "банки ипотека",
                "text": "банки ипотека",
                "state": "on",
            },
            {
                "id": "k2",
                "campaign_id": "c1",
                "ad_group_id": "g1",
                "phrase": "ипотека -банк",
                "text": "ипотека -банк",
                "state": "on",
            },
        ],
        extensions=[],
    )
    assert rule(ctx, {}) == []


def test_duplicate_keywords_with_overlap_cross_campaign_on_fixture_semantics() -> None:
    data = load_fixture_dict()
    campaigns = campaigns_normalized_from_fixture(data)
    groups: list[dict] = []
    keywords: list[dict] = []
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
                }
            )
            for kw in g.get("keywords", []) or []:
                keywords.append(
                    {
                        "id": str(kw.get("keyword_id")),
                        "campaign_id": cid,
                        "ad_group_id": gid,
                        "text": kw.get("text"),
                        "phrase": kw.get("text"),
                        "state": kw.get("status"),
                    }
                )
    rule = build_l1_rule_registry()["DUPLICATE_KEYWORDS_WITH_OVERLAP"]
    ctx = L1Context(
        account_id="fixture",
        campaigns=campaigns,
        groups=groups,
        ads=[],
        keywords=keywords,
        extensions=[],
    )
    findings = rule(ctx, {})
    cross = [
        f
        for f in findings
        if f.evidence.get("overlap_kind") == "cross_campaign"
        and {f.evidence.get("left_campaign_id"), f.evidence.get("right_campaign_id")} == {"C200", "C300"}
    ]
    assert cross, "expected cross-campaign overlap C200/C300 on fixture"
    cross_group_suppressed = [
        f
        for f in findings
        if f.evidence.get("overlap_kind") == "cross_group"
        and f.evidence.get("left_campaign_id") == "C200"
        and {f.evidence.get("left_group_id"), f.evidence.get("right_group_id")} == {"G2004", "G2005"}
    ]
    assert not cross_group_suppressed, "G2004 has minus-word «центр» — overlap with G2005 tail must be suppressed"


def test_geo_text_targeting_mismatch_uses_yandex_region_ids() -> None:
    rule = build_l1_rule_registry()["GEO_TEXT_TARGETING_MISMATCH"]
    base_ad = {
        "id": "a1",
        "campaign_id": "c1",
        "ad_group_id": "g1",
        "status": "accepted",
        "state": "on",
        "title": "Купить квартиру москва",
        "text": "",
    }
    ctx_ok = L1Context(
        account_id="a",
        campaigns=[{"id": "c1", "status": "active", "geo": []}],
        groups=[{"id": "g1", "campaign_id": "c1", "status": "active", "region_ids": [213]}],
        ads=[base_ad],
        keywords=[],
        extensions=[],
    )
    assert rule(ctx_ok, {}) == []

    ctx_bad = L1Context(
        account_id="a",
        campaigns=[{"id": "c1", "status": "active", "geo": []}],
        groups=[{"id": "g1", "campaign_id": "c1", "status": "active", "region_ids": [213]}],
        ads=[{**base_ad, "title": "Купить квартиру спб"}],
        keywords=[],
        extensions=[],
    )
    findings = rule(ctx_bad, {})
    assert len(findings) == 1
    assert findings[0].evidence["mentioned_city"] == "санкт-петербург"


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
    sums = findings[0].evidence.get("ads_image_summaries") or []
    assert len(sums) == 2
    assert all(s.get("caption_ru") == "изображение не указано" for s in sums)


def test_duplicate_ads_not_fired_when_same_text_but_different_image_id() -> None:
    rule = build_l1_rule_registry()["DUPLICATE_ADS"]
    base = {
        "ad_group_id": "g1",
        "campaign_id": "c1",
        "status": "active",
        "state": "on",
        "title": "T",
        "text": "X",
        "url": "https://x.com",
    }
    ctx = L1Context(
        account_id="a",
        campaigns=[],
        groups=[],
        keywords=[],
        extensions=[],
        ads=[
            {**base, "id": "a1", "image": {"id": 101, "name": "square", "width": 1080, "height": 1080}},
            {**base, "id": "a2", "image": {"id": 202, "name": "vertical", "width": 900, "height": 1200}},
        ],
    )
    assert rule(ctx, {}) == []


def test_duplicate_ads_fired_when_same_text_and_same_image_id() -> None:
    rule = build_l1_rule_registry()["DUPLICATE_ADS"]
    base = {
        "ad_group_id": "g1",
        "campaign_id": "c1",
        "status": "active",
        "state": "on",
        "title": "T",
        "text": "X",
        "url": "https://x.com",
        "image": {"id": 555, "name": "creative_a", "width": 1200, "height": 628},
    }
    ctx = L1Context(
        account_id="a",
        campaigns=[],
        groups=[],
        keywords=[],
        extensions=[],
        ads=[{**base, "id": "a1"}, {**base, "id": "a2"}],
    )
    findings = rule(ctx, {})
    assert len(findings) == 1
    assert findings[0].evidence.get("shared_image_fingerprint") == "id:555"


@pytest.mark.parametrize(
    ("left", "right"),
    [
        (_LONG_IPOTEKA_MINUS_TAIL, "сельская ипотека -2026"),
        ("семейная ипотека -2026 -год -условие", "семейная ипотека условия -2026"),
        ("ипотека 2026 -год -сельский -семейный -условие", "ипотека в 2026 году условия"),
        ("ипотека 2026 -год -сельский -семейный -условие", "семейная ипотека в 2026 году"),
        (_LONG_IPOTEKA_MINUS_TAIL, "ипотека на жилье"),
        (_LONG_IPOTEKA_MINUS_TAIL, "семейная ипотека 2026 -год -условие"),
        ("новостройки -квартира -рассрочка", "новостройки в рассрочку"),
        (_LONG_IPOTEKA_MINUS_TAIL, "ипотека выксе"),
        ("семейная ипотека 2026 -год -условие", "семейная ипотека в 2026 году"),
        ("ипотека в 2026 году -условие -семейный", "семейная ипотека в 2026 году"),
        ("купить квартиру -выкса", "купить квартиру в выксе"),
        (_LONG_IPOTEKA_MINUS_TAIL, "сельская ипотека 2026"),
        (_LONG_IPOTEKA_MINUS_TAIL, "семейная ипотека -2026 -год -условие"),
        ("условия ипотеки 2026 -год -семейный", "условия семейной ипотеки в 2026"),
        ("семейная ипотека -2026 -год -условие", "семейная ипотека в 2026 году"),
        ("ипотека 2026 -год -сельский -семейный -условие", "семейная ипотека 2026 -год -условие"),
        ("ипотека в 2026 году -условие -семейный", "ипотека в 2026 году условия"),
        ("ипотека 2026 -год -сельский -семейный -условие", "ипотека в 2026 году -условие -семейный"),
        ("ипотека 2026 -год -сельский -семейный -условие", "сельская ипотека 2026"),
    ],
)
def test_duplicate_keywords_with_overlap_suppressed_on_production_pairs(left: str, right: str) -> None:
    rule = build_l1_rule_registry()["DUPLICATE_KEYWORDS_WITH_OVERLAP"]
    assert rule(_ctx_dup_kw_cross_groups(left, right), {}) == []


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("можно ипотеку", "можно ли семейную ипотеку"),
        ("ипотека в 2026 году условия", "семейная ипотека в 2026 году"),
        (_LONG_IPOTEKA_MINUS_TAIL, "семейная ипотека условия -2026"),
        (_LONG_IPOTEKA_MINUS_TAIL, "ипотека в 2026 году -условие -семейный"),
        ("квартира от застройщика нижний рассрочка", "рассрочка от застройщика -квартира"),
        ("жк квартиру от застройщика", "как взять квартиру в рассрочку от застройщика"),
        ("ипотека в 2026 году условия", _LONG_IPOTEKA_MINUS_TAIL),
        ("как взять квартиру в рассрочку от застройщика", "квартира в рассрочку от застройщика -взять -нижний"),
        (_LONG_IPOTEKA_MINUS_TAIL, "семейная ипотека года -2026"),
        (_LONG_IPOTEKA_MINUS_TAIL, "семейная ипотека в 2026 году"),
    ],
)
def test_duplicate_keywords_with_overlap_fires_on_production_pairs(left: str, right: str) -> None:
    rule = build_l1_rule_registry()["DUPLICATE_KEYWORDS_WITH_OVERLAP"]
    assert len(rule(_ctx_dup_kw_cross_groups(left, right), {})) >= 1


def test_duplicate_keywords_minus_god_never_covers_digit_year_token() -> None:
    """Минус «год» не снимает пересечение с плюс-токеном «2026» (разные сущности)."""
    rule = build_l1_rule_registry()["DUPLICATE_KEYWORDS_WITH_OVERLAP"]
    ctx = _ctx_dup_kw_cross_groups("ипотека 2026", "ипотека -год")
    assert len(rule(ctx, {})) >= 1


def test_duplicate_keywords_minus_digit_year_never_covers_god_lexeme() -> None:
    """Минус «2026» не снимает пересечение с плюс-токеном «году» (симметрично)."""
    rule = build_l1_rule_registry()["DUPLICATE_KEYWORDS_WITH_OVERLAP"]
    ctx = _ctx_dup_kw_cross_groups("ипотека в 2026 году", "ипотека -2026")
    assert len(rule(ctx, {})) >= 1
