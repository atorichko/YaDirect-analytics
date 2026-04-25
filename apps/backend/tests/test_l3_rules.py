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


def test_unresolved_placeholder_ignores_yandex_dynamic_macros() -> None:
    rule = build_l3_rule_registry()["UNRESOLVED_PLACEHOLDER_IN_URL"]
    ctx = L3Context(
        account_id="acc1",
        ads=[
            {
                "id": "a1",
                "campaign_id": "c1",
                "ad_group_id": "g1",
                "url": "https://example.com/land?utm_term={keyword}&utm_source=yandex",
            }
        ],
        extensions=[],
    )
    assert rule(ctx, {"recommendation_ru": "fix"}) == []


def test_unresolved_placeholder_ignores_calltouch_style_yandex_macros() -> None:
    rule = build_l3_rule_registry()["UNRESOLVED_PLACEHOLDER_IN_URL"]
    url = (
        "https://mrqz.me/bm36?calltouch_tm=yd_c:{campaign_id}_gb:{gbid}_ad:{ad_id}_"
        "ph:{phrase_id}_st:{source_type}_pt:{position_type}_p:{position}_s:{source}_"
        "dt:{device_type}_reg:{region_id}_ret:{retargeting_id}_apt:{addphrasestext}"
    )
    ctx = L3Context(
        account_id="acc1",
        ads=[{"id": "a1", "campaign_id": "c1", "ad_group_id": "g1", "url": url}],
        extensions=[],
    )
    assert rule(ctx, {"recommendation_ru": "fix"}) == []


def test_unresolved_placeholder_ignores_percent_encoded_utf8_in_query() -> None:
    """Percent-encoded Cyrillic in param values must not match old %…% placeholder heuristic."""
    rule = build_l3_rule_registry()["UNRESOLVED_PLACEHOLDER_IN_URL"]
    url = (
        "https://mrqz.me/bm36?utm1=%D0%9D%D0%B5%20%D1%85%D0%BE%D1%82%D0%B8%D1%82%D0%B5%20%D1%84%D1%80%D0%B0%D0%B3"
        "&utm2=test&calltouch_tm=yd_c:{campaign_id}_gb:{gbid}_ad:{ad_id}_ph:{phrase_id}_st:{source_type}_"
        "pt:{position_type}_p:{position}_s:{source}_dt:{device_type}_reg:{region_id}_ret:{retargeting_id}_"
        "apt:{addphrasestext}"
    )
    ctx = L3Context(
        account_id="acc1",
        ads=[{"id": "17693253313", "campaign_id": "c1", "ad_group_id": "g1", "url": url}],
        extensions=[],
    )
    assert rule(ctx, {"recommendation_ru": "fix"}) == []


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


def test_missing_required_utm_suppressed_when_campaign_tracking_has_params() -> None:
    rule = build_l3_rule_registry()["MISSING_REQUIRED_UTM"]
    required = ["utm_source", "utm_medium", "utm_campaign"]
    tracking = "https://track.example/?utm_source=yandex&utm_medium=cpc&utm_campaign=x"
    ctx = L3Context(
        account_id="acc1",
        ads=[{"id": "a1", "campaign_id": "c1", "ad_group_id": "g1", "url": "https://landing.example/noutm"}],
        extensions=[],
        campaigns=[{"id": "c1", "tracking_template": tracking}],
        groups=[],
    )
    assert rule(ctx, {"required_utm_params": required}) == []


def test_missing_required_utm_suppressed_when_group_tracking_has_params() -> None:
    rule = build_l3_rule_registry()["MISSING_REQUIRED_UTM"]
    required = ["utm_source", "utm_medium", "utm_campaign"]
    tracking = "https://track.example/?utm_source=yandex&utm_medium=cpc&utm_campaign=x"
    ctx = L3Context(
        account_id="acc1",
        ads=[{"id": "a1", "campaign_id": "c1", "ad_group_id": "g1", "url": "https://landing.example/noutm"}],
        extensions=[],
        campaigns=[],
        groups=[{"id": "g1", "campaign_id": "c1", "tracking_url": tracking}],
    )
    assert rule(ctx, {"required_utm_params": required}) == []


def test_missing_required_utm_suppressed_when_campaign_url_parameters_query_string() -> None:
    rule = build_l3_rule_registry()["MISSING_REQUIRED_UTM"]
    required = ["utm_source", "utm_medium", "utm_campaign"]
    url_parameters = (
        "utm_source=yandex&utm_medium=cpc&"
        "utm_campaign={source_type}_cid:{campaign_id}_{campaign_name_lat}"
    )
    ctx = L3Context(
        account_id="acc1",
        ads=[{"id": "a1", "campaign_id": "c1", "ad_group_id": "g1", "url": "https://mrqz.me/bm36"}],
        extensions=[],
        campaigns=[{"id": "c1", "url_parameters": url_parameters}],
        groups=[],
    )
    assert rule(ctx, {"required_utm_params": required}) == []


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


def test_inconsistent_utm_account_wide_requires_multiple_campaigns() -> None:
    rule = build_l3_rule_registry()["INCONSISTENT_UTM_PATTERN"]
    ctx = L3Context(
        account_id="acc_mix",
        ads=[
            {
                "id": "a1",
                "campaign_id": "c1",
                "ad_group_id": "g1",
                "url": "https://a.example/?utm_source=yandex&utm_medium=cpc&utm_campaign=z",
            },
            {
                "id": "a2",
                "campaign_id": "c2",
                "ad_group_id": "g2",
                "url": "https://b.example/?utm_source=yd&utm_campaign=z",
            },
        ],
        extensions=[],
    )
    findings = rule(ctx, {})
    account_f = [f for f in findings if f.evidence.get("scope") == "account"]
    assert len(account_f) == 1
    camps = account_f[0].evidence.get("campaigns_with_mixed_patterns") or []
    assert set(camps) == {"c1", "c2"}


def test_invalid_utm_ignores_percent_encoded_human_text_tokens() -> None:
    rule = build_l3_rule_registry()["INVALID_UTM"]
    url = (
        "https://example.com/?utm_source=yandex&"
        "%D0%A0%D0%B0%D1%81%D1%81%D1%80%D0%BE%D1%87%D0%BA%D0%B0%20"
        "%D0%BE%D1%82%20%D0%B7%D0%B0%D1%81%D1%82%D1%80%D0%BE%D0%B9%D1%89%D0%B8%D0%BA%D0%B0!&"
        "utm_medium=cpc&utm_campaign=cmp"
    )
    ctx = L3Context(
        account_id="acc1",
        ads=[{"id": "a1", "campaign_id": "c1", "ad_group_id": "g1", "url": url}],
        extensions=[],
    )
    assert rule(ctx, {}) == []


def test_empty_or_technical_params_ignores_percent_encoded_human_text_tokens() -> None:
    rule = build_l3_rule_registry()["EMPTY_OR_TECHNICAL_URL_PARAMS"]
    url = (
        "https://example.com/?utm_source=yandex&"
        "%D0%A2%D0%B5%D0%BA%D1%81%D1%82%20%D0%B1%D0%B5%D0%B7%20%D0%BA%D0%BB%D1%8E%D1%87%D0%B0&"
        "utm_medium=cpc"
    )
    ctx = L3Context(
        account_id="acc1",
        ads=[{"id": "a1", "campaign_id": "c1", "ad_group_id": "g1", "url": url}],
        extensions=[],
    )
    assert rule(ctx, {}) == []
