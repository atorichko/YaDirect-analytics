"""Загрузка и конвертация встроенного rule-catalog.json (как в UI и в Docker-образе бэкенда)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.services.l1_rules import build_l1_rule_registry
from app.services.l2_rules import build_l2_rule_registry
from app.services.l3_rules import build_l3_rule_registry


def bump_semver_patch(ver: str) -> str:
    s = ver.strip()
    m = re.match(r"^(\d+)\.(\d+)\.(\d+)$", s)
    if m:
        return f"{m.group(1)}.{m.group(2)}.{int(m.group(3)) + 1}"
    m = re.match(r"^(\d+)\.(\d+)$", s)
    if m:
        return f"{m.group(1)}.{m.group(2)}.1"
    return f"{s}.1"


def resolve_bundled_rule_catalog_path() -> Path:
    """Путь к JSON каталога: BUNDLED_RULE_CATALOG_PATH, затем Docker bundle, затем монорепо."""
    override = (settings.bundled_rule_catalog_path or "").strip()
    if override:
        p = Path(override)
        if p.is_file():
            return p
    docker_bundle = Path("/app/frontend-data/rule-catalog.json")
    if docker_bundle.is_file():
        return docker_bundle
    here = Path(__file__).resolve()
    for ancestor in here.parents:
        candidate = ancestor / "apps" / "frontend" / "src" / "data" / "rule-catalog.json"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "rule-catalog.json not found. Set BUNDLED_RULE_CATALOG_PATH or ensure "
        "/app/frontend-data/rule-catalog.json exists in the image."
    )


def load_bundled_rule_catalog_raw() -> dict[str, Any]:
    path = resolve_bundled_rule_catalog_path()
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        msg = "Bundled rule catalog must be a JSON object"
        raise ValueError(msg)
    return data


def check_type_for_rule(rule: dict[str, Any], l1: set[str], l2: set[str], l3: set[str]) -> str:
    code = str(rule.get("rule_code") or "")
    level = str(rule.get("level") or "")
    if level == "L1" and code in l1:
        return "deterministic"
    if level == "L2" and code in l2:
        return "deterministic"
    if level == "L3" and code in l3:
        return "deterministic"
    return "ai_assisted"


def convert_frontend_catalog_to_api_payload(raw: dict[str, Any], catalog_version: str | None) -> dict[str, Any]:
    """Тот же маппинг, что в scripts/upload_rule_catalog_api.py → тело POST /rule-catalogs."""
    l1 = set(build_l1_rule_registry())
    l2 = set(build_l2_rule_registry())
    l3 = set(build_l3_rule_registry())
    rules_out: list[dict[str, Any]] = []
    for r in raw.get("rules") or []:
        if not isinstance(r, dict) or not r.get("rule_code"):
            continue
        desc_parts = [str(r.get("detection_logic") or "").strip(), str(r.get("fail_condition") or "").strip()]
        desc = ". ".join(p for p in desc_parts if p)[:512]
        meta_keys = {
            "rule_code",
            "name_ru",
            "severity",
            "level",
            "recommendation_ru",
            "detection_logic",
            "fail_condition",
        }
        config = {k: v for k, v in r.items() if k not in meta_keys}
        rules_out.append(
            {
                "rule_code": str(r["rule_code"]),
                "rule_name": str(r.get("name_ru") or r["rule_code"]),
                "rule_description": desc or None,
                "fix_recommendation": (str(r.get("recommendation_ru")).strip() or None) if r.get("recommendation_ru") else None,
                "level": str(r["level"]),
                "severity": str(r["severity"]),
                "check_type": check_type_for_rule(r, l1, l2, l3),
                "enabled": True,
                "config": config,
            }
        )
    return {
        "catalog_version": catalog_version or str(raw.get("catalog_version") or "1.0.0"),
        "platform": str(raw.get("platform") or "yandex_direct"),
        "included_levels": list(raw.get("included_levels") or ["L1", "L2", "L3"]),
        "description": raw.get("description"),
        "rules": rules_out,
    }
