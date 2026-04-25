from app.services.l2_rules import L2Context, build_l2_rule_registry
from tests.fixture_loader import (
    campaigns_normalized_from_fixture,
    load_fixture_dict,
    metrika_goals_from_fixture,
)


def test_campaign_without_metrika_counter_rule() -> None:
    rule = build_l2_rule_registry()["CAMPAIGN_WITHOUT_METRIKA_COUNTER"]
    ctx = L2Context(
        account_id="acc1",
        campaigns=[{"id": "c1", "status": "active", "metrika_counter_id": None}],
    )
    assert len(rule(ctx, {})) == 1
    ctx_ok = L2Context(
        account_id="acc1",
        campaigns=[{"id": "c1", "status": "active", "metrika_counter_id": "123"}],
    )
    assert rule(ctx_ok, {}) == []
    ctx_multi = L2Context(
        account_id="acc1",
        campaigns=[
            {
                "id": "c1",
                "status": "active",
                "metrika_counter_id": None,
                "metrika_counter_ids": ["111", "222"],
            },
        ],
    )
    assert rule(ctx_multi, {}) == []
    ctx_counter_ids = L2Context(
        account_id="acc1",
        campaigns=[
            {
                "id": "c1",
                "status": "active",
                "metrika_counter_id": None,
                "CounterIds": [57157849, 98751909, 98801492],
            },
        ],
    )
    assert rule(ctx_counter_ids, {}) == []


def test_campaign_without_metrika_goals_rule() -> None:
    rule = build_l2_rule_registry()["CAMPAIGN_WITHOUT_METRIKA_GOALS"]
    ctx = L2Context(
        account_id="acc1",
        campaigns=[{"id": "c1", "status": "ON", "metrika_counter_id": "999", "goal_ids": []}],
    )
    assert len(rule(ctx, {})) == 1
    ctx_no_counter = L2Context(
        account_id="acc1",
        campaigns=[{"id": "c1", "status": "active", "metrika_counter_id": None, "goal_ids": []}],
    )
    assert rule(ctx_no_counter, {}) == []
    ctx_ok = L2Context(
        account_id="acc1",
        campaigns=[{"id": "c1", "status": "active", "metrika_counter_id": "1", "goal_ids": ["g1"]}],
    )
    assert rule(ctx_ok, {}) == []
    ctx_ok_numeric_goal = L2Context(
        account_id="acc1",
        campaigns=[{"id": "c1", "status": "ON", "metrika_counter_ids": ["98751909"], "goal_ids": ["362433471"]}],
    )
    assert rule(ctx_ok_numeric_goal, {}) == []


def test_conversion_strategy_without_metrika_rule() -> None:
    rule = build_l2_rule_registry()["CONVERSION_STRATEGY_WITHOUT_METRIKA"]
    ctx = L2Context(
        account_id="acc1",
        campaigns=[{"id": "c1", "strategy_type": "target_cpa", "metrika_counter_id": None}],
    )
    findings = rule(ctx, {})
    assert len(findings) == 1
    assert findings[0].campaign_external_id == "c1"


def test_conversion_strategy_without_goal_rule() -> None:
    rule = build_l2_rule_registry()["CONVERSION_STRATEGY_WITHOUT_GOAL"]
    ctx = L2Context(
        account_id="acc1",
        campaigns=[
            {"id": "c1", "strategy_type": "target_cpa", "metrika_counter_id": "ctr_001", "goal_ids": []},
        ],
    )
    findings = rule(ctx, {})
    assert len(findings) == 1


def test_conversion_strategy_with_unavailable_goal_rule() -> None:
    rule = build_l2_rule_registry()["CONVERSION_STRATEGY_WITH_UNAVAILABLE_GOAL"]
    ctx = L2Context(
        account_id="acc1",
        campaigns=[
            {"id": "c1", "strategy_type": "target_cpa", "metrika_counter_id": "ctr_001", "goal_ids": ["g99"]},
        ],
        metrika_goals=[{"goal_id": "g99", "status": "deleted", "access": "revoked"}],
    )
    findings = rule(ctx, {})
    assert len(findings) == 1
    assert findings[0].evidence.get("problem_goals")


def test_yandex_fixture_l2_metrika_and_learning_campaigns() -> None:
    data = load_fixture_dict()
    ctx = L2Context(
        account_id="fixture",
        campaigns=campaigns_normalized_from_fixture(data),
        metrika_goals=metrika_goals_from_fixture(data),
    )
    reg = build_l2_rule_registry()
    c400_metrika = [f for f in reg["CONVERSION_STRATEGY_WITHOUT_METRIKA"](ctx, {}) if f.campaign_external_id == "C400"]
    c400_goal = [f for f in reg["CONVERSION_STRATEGY_WITHOUT_GOAL"](ctx, {}) if f.campaign_external_id == "C400"]
    assert len(c400_metrika) == 1
    assert len(c400_goal) == 1

    c410 = [f for f in reg["CONVERSION_STRATEGY_WITH_UNAVAILABLE_GOAL"](ctx, {}) if f.campaign_external_id == "C410"]
    assert len(c410) == 1

    policy = data.get("policy") or {}
    min_conv = int(policy.get("min_conversions_for_learning") or 10)
    c420 = [
        f
        for f in reg["CONVERSION_STRATEGY_WITHOUT_LEARNING_DATA"](ctx, {"min_conversions_for_learning": min_conv})
        if f.campaign_external_id == "C420"
    ]
    assert len(c420) == 1


def test_conversion_strategy_without_learning_data_rule() -> None:
    rule = build_l2_rule_registry()["CONVERSION_STRATEGY_WITHOUT_LEARNING_DATA"]
    ctx = L2Context(
        account_id="acc1",
        campaigns=[
            {
                "id": "c1",
                "strategy_type": "conversion_maximization",
                "stats": {"conversions": 12, "analysis_period_days": 14},
            }
        ],
    )
    findings = rule(ctx, {"min_conversions_for_learning": 30})
    assert len(findings) == 1
    assert findings[0].campaign_external_id == "c1"


def test_campaign_chronic_budget_limit_rule() -> None:
    rule = build_l2_rule_registry()["CAMPAIGN_CHRONIC_BUDGET_LIMIT"]
    ctx = L2Context(
        account_id="acc1",
        campaigns=[
            {
                "id": "c1",
                "stats": {
                    "budget_limited_days": 5,
                    "analysis_period_days": 14,
                    "avg_hour_of_budget_exhaustion": 13.0,
                },
            }
        ],
    )
    findings = rule(ctx, {"budget_limited_days_threshold": 3})
    assert len(findings) == 1
    assert findings[0].evidence["budget_limited_days"] == 5
