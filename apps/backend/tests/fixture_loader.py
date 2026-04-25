"""Helpers to load repo-root test fixture (yandex_direct_audit_test_account) for tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def fixture_path() -> Path:
    """Resolve test.txt: bundled copy, repo root, or any ancestor (monorepo / Docker bind mounts)."""
    here = Path(__file__).resolve()
    bundled = here.parent / "fixtures" / "audit_fixture.json"
    if bundled.is_file():
        return bundled
    for ancestor in here.parents:
        candidate = ancestor / "test.txt"
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        f"Fixture not found. Tried {bundled} and test.txt in ancestors of {here}. "
        "Place test.txt at repo root or add tests/fixtures/audit_fixture.json."
    )


def load_fixture_dict() -> dict[str, Any]:
    path = fixture_path()
    return json.loads(path.read_text(encoding="utf-8"))


def metrika_goals_from_fixture(data: dict[str, Any]) -> list[dict[str, Any]]:
    metrika = data.get("metrika") or {}
    goals = metrika.get("goals")
    if not isinstance(goals, list):
        return []
    return [g for g in goals if isinstance(g, dict)]


def campaigns_normalized_from_fixture(data: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for c in data.get("campaigns", []) or []:
        cid = str(c.get("campaign_id") or "")
        if not cid:
            continue
        region_union: set[int] = set()
        for g in c.get("groups", []) or []:
            for rid in g.get("region_ids") or []:
                try:
                    region_union.add(int(rid))
                except (TypeError, ValueError):
                    continue
        row: dict[str, Any] = {
            "id": cid,
            "name": c.get("campaign_name"),
            "status": c.get("status"),
            "type": c.get("type") or c.get("strategy_type"),
            "strategy_type": c.get("strategy_type"),
            "metrika_counter_id": c.get("metrika_counter_id"),
            "metrika_counter_ids": c.get("metrika_counter_ids") or [],
            "metrika_counters": c.get("metrika_counters") or [],
            "counter_ids": c.get("counter_ids") or c.get("CounterIds") or [],
            "goal_ids": c.get("goal_ids") or [],
            "daily_budget": c.get("daily_budget"),
            "stats": c.get("stats") or {},
            "geo": c.get("geo") or [],
            "region_ids": sorted(region_union),
            "negative_keywords": c.get("negative_keywords") or [],
        }
        for tk in ("tracking_url", "tracking_template", "campaign_tracking_url", "mobile_app_tracking_url", "href"):
            if c.get(tk):
                row[tk] = c[tk]
        out.append(row)
    return out


def ad_groups_normalized_from_fixture(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Нормализованные группы (как в import_yandex_fixture) — для L3 UTM по иерархии кампания/группа."""
    out: list[dict[str, Any]] = []
    for c in data.get("campaigns", []) or []:
        cid = str(c.get("campaign_id") or "")
        for g in c.get("groups", []) or []:
            gid = str(g.get("group_id") or "")
            if not gid:
                continue
            row: dict[str, Any] = {
                "id": gid,
                "campaign_id": cid,
                "name": g.get("group_name"),
                "status": g.get("status"),
                "serving_status": g.get("serving_status"),
                "autotargeting": g.get("autotargeting"),
                "region_ids": g.get("region_ids") or [],
                "negative_keywords": g.get("negative_keywords") or [],
                "audiences": g.get("audiences") or [],
                "retargeting_lists": g.get("retargeting_lists") or g.get("RetargetingLists") or [],
            }
            for tk in ("tracking_url", "tracking_template", "campaign_tracking_url", "mobile_app_tracking_url", "href"):
                if g.get(tk):
                    row[tk] = g[tk]
            out.append(row)
    return out


def l1_extensions_from_fixture(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Build extension rows like SnapshotEntityType.extension normalized_snapshot (fixture tree shape)."""
    out: list[dict[str, Any]] = []
    for c in data.get("campaigns", []) or []:
        campaign_id = str(c.get("campaign_id") or "")
        for g in c.get("groups", []) or []:
            group_id = str(g.get("group_id") or "")
            for ad in g.get("ads", []) or []:
                ad_id = str(ad.get("ad_id") or "")
                if not ad_id:
                    continue
                sl = ad.get("sitelinks")
                sitelinks = sl if isinstance(sl, list) else []
                out.append(
                    {
                        "id": f"ext:{ad_id}",
                        "campaign_id": campaign_id,
                        "ad_group_id": group_id,
                        "ad_id": ad_id,
                        "sitelinks": sitelinks,
                        "callouts": ad.get("callouts") or [],
                        "display_url": ad.get("display_url"),
                        "contact_info": ad.get("contact_info"),
                        "image": ad.get("image"),
                    }
                )
    return out
