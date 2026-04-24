from __future__ import annotations

import json
from pathlib import Path

from app.services.l1_rules import build_l1_rule_registry
from app.services.l2_rules import build_l2_rule_registry
from app.services.l3_rules import build_l3_rule_registry
from tests.fixture_loader import load_fixture_dict


def _catalog_file_path() -> Path:
    here = Path(__file__).resolve()
    bundled = here.parent / "fixtures" / "каталог правил.json"
    if bundled.is_file():
        return bundled
    for ancestor in here.parents:
        candidate = ancestor / "каталог правил.json"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"Could not find `каталог правил.json` starting from {here}")


def _catalog_rules() -> list[dict]:
    payload = json.loads(_catalog_file_path().read_text(encoding="utf-8"))
    rules = payload.get("rules")
    assert isinstance(rules, list), "catalog must contain `rules` list"
    return [r for r in rules if isinstance(r, dict)]


def test_catalog_contains_all_fixture_expected_rule_codes() -> None:
    expected = load_fixture_dict().get("expected_rule_coverage") or []
    assert isinstance(expected, list) and expected, "fixture must define expected_rule_coverage"

    catalog_codes = {str(r.get("rule_code")) for r in _catalog_rules() if r.get("rule_code")}
    missing = sorted({str(code) for code in expected if str(code) not in catalog_codes})
    assert not missing, f"catalog is missing expected fixture rule codes: {missing}"


def test_catalog_rule_levels_match_deterministic_registries() -> None:
    expected_level_by_rule: dict[str, str] = {}
    expected_level_by_rule.update({code: "L1" for code in build_l1_rule_registry()})
    expected_level_by_rule.update({code: "L2" for code in build_l2_rule_registry()})
    expected_level_by_rule.update({code: "L3" for code in build_l3_rule_registry()})

    mismatches: list[str] = []
    for rule in _catalog_rules():
        code = str(rule.get("rule_code") or "")
        level = str(rule.get("level") or "")
        if not code or code not in expected_level_by_rule:
            continue
        expected_level = expected_level_by_rule[code]
        if level != expected_level:
            mismatches.append(f"{code}: catalog={level}, registry={expected_level}")

    assert not mismatches, "catalog level mismatches for implemented deterministic rules: " + ", ".join(mismatches)
