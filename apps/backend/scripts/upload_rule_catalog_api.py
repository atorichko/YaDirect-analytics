#!/usr/bin/env python3
"""Загрузить rule-catalog.json в API и активировать каталог (нужен Bearer-токен админа).

Пример:
  export API_BASE_URL="https://example.ru/YaDirect-analytics/api/v1"
  export ADMIN_ACCESS_TOKEN="eyJ..."
  python scripts/upload_rule_catalog_api.py

При конфликте версии (409) задайте новую:
  python scripts/upload_rule_catalog_api.py --catalog-version 1.0.1
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.services.l1_rules import build_l1_rule_registry
from app.services.l2_rules import build_l2_rule_registry
from app.services.l3_rules import build_l3_rule_registry


def _rule_catalog_path() -> Path:
    docker_bundle = Path("/app/frontend-data/rule-catalog.json")
    if docker_bundle.is_file():
        return docker_bundle
    for ancestor in Path(__file__).resolve().parents:
        candidate = ancestor / "apps" / "frontend" / "src" / "data" / "rule-catalog.json"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError("rule-catalog.json not found")


def _check_type_for_rule(rule: dict, l1: set[str], l2: set[str], l3: set[str]) -> str:
    code = str(rule.get("rule_code") or "")
    level = str(rule.get("level") or "")
    if level == "L1" and code in l1:
        return "deterministic"
    if level == "L2" and code in l2:
        return "deterministic"
    if level == "L3" and code in l3:
        return "deterministic"
    return "ai_assisted"


def _convert_payload(raw: dict, catalog_version: str | None) -> dict:
    l1 = set(build_l1_rule_registry())
    l2 = set(build_l2_rule_registry())
    l3 = set(build_l3_rule_registry())
    rules_out: list[dict] = []
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
                "check_type": _check_type_for_rule(r, l1, l2, l3),
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


def _request_json(method: str, url: str, token: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    if body is not None:
        req.add_header("Content-Type", "application/json; charset=utf-8")
    with urlopen(req, timeout=120) as resp:
        payload = resp.read().decode("utf-8")
        return json.loads(payload) if payload else {}


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload and activate rule catalog via API")
    parser.add_argument("--catalog-version", default=None, help="Override catalog_version (required if version exists in DB)")
    parser.add_argument("--dry-run", action="store_true", help="Print JSON body and exit")
    args = parser.parse_args()

    base = os.environ.get("API_BASE_URL", "http://127.0.0.1:8010/api/v1").rstrip("/")
    token = os.environ.get("ADMIN_ACCESS_TOKEN", "").strip()
    if not token and not args.dry_run:
        print("Set ADMIN_ACCESS_TOKEN (Bearer for admin user)", file=sys.stderr)
        sys.exit(1)

    path = _rule_catalog_path()
    raw = json.loads(path.read_text(encoding="utf-8"))
    body = _convert_payload(raw, args.catalog_version)

    if args.dry_run:
        print(json.dumps(body, ensure_ascii=False, indent=2))
        return

    upload_url = f"{base}/rule-catalogs"
    try:
        created = _request_json("POST", upload_url, token, body)
    except HTTPError as exc:
        err = exc.read().decode("utf-8", errors="replace")
        print(f"POST {upload_url} failed: {exc.code}\n{err}", file=sys.stderr)
        if exc.code == 409:
            print("Hint: pass --catalog-version with a new value (e.g. 1.0.1)", file=sys.stderr)
        sys.exit(1)

    catalog_id = created.get("id")
    if not catalog_id:
        print("Unexpected response:", created, file=sys.stderr)
        sys.exit(1)

    act_url = f"{base}/rule-catalogs/{catalog_id}/activate"
    try:
        active = _request_json("POST", act_url, token, {})
    except HTTPError as exc:
        err = exc.read().decode("utf-8", errors="replace")
        print(f"POST {act_url} failed: {exc.code}\n{err}", file=sys.stderr)
        sys.exit(1)

    print(json.dumps({"uploaded": created, "activated": active}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
