"""Guard: every rule_code listed in test fixture expected_rule_coverage has a handler."""

from __future__ import annotations

from app.services.l1_rules import build_l1_rule_registry
from app.services.l2_rules import build_l2_rule_registry
from app.services.l3_rules import build_l3_rule_registry
from tests.fixture_loader import load_fixture_dict


def test_expected_rule_coverage_has_handlers() -> None:
    data = load_fixture_dict()
    expected = data.get("expected_rule_coverage")
    assert isinstance(expected, list) and expected, "fixture must define expected_rule_coverage"

    implemented = (
        set(build_l1_rule_registry()) | set(build_l2_rule_registry()) | set(build_l3_rule_registry())
    )
    missing = sorted({str(code) for code in expected if str(code) not in implemented})
    assert not missing, f"expected_rule_coverage lists codes without registry handlers: {missing}"
