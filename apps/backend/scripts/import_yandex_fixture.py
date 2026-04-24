"""Import yandex_direct_audit_test_account JSON fixture into entity_snapshots (+ optional Metrika goals)."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.core.database import AsyncSessionLocal
from app.models.entity_snapshot import SnapshotEntityType
from app.repositories.ad_account import AdAccountRepository
from app.repositories.entity_snapshot import EntitySnapshotRepository


def _hash(data: object) -> str:
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def normalize_health(item: dict) -> dict:
    ssl = item.get("ssl_check") or {}
    return {
        "status_code": item.get("status_code"),
        "network_error": item.get("network_error"),
        "ssl_error": ssl.get("error") if isinstance(ssl, dict) else None,
        "redirect_chain": item.get("redirect_chain") or [],
        "final_url": item.get("final_url"),
    }


async def import_fixture(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    account_src = payload["account"]
    campaigns = payload.get("campaigns", [])
    checks = payload.get("technical_checks", [])
    check_map = {str(x.get("checked_url")): normalize_health(x) for x in checks if isinstance(x, dict) and x.get("checked_url")}
    metrika = payload.get("metrika") or {}
    now = datetime.now(timezone.utc)

    async with AsyncSessionLocal() as session:
        accounts = AdAccountRepository(session)
        snapshots = EntitySnapshotRepository(session)

        account = await accounts.get_by_external_id(account_src["account_id"])
        login = str(account_src.get("account_id") or "fixture_account").lower()
        if account is None:
            account = await accounts.create(
                external_id=account_src["account_id"],
                name=account_src.get("account_name") or "Fixture account",
                login=login,
            )
        else:
            account.name = account_src.get("account_name") or account.name
            if account.login != login:
                account.login = login

        counts = {"campaigns": 0, "groups": 0, "ads": 0, "keywords": 0, "extensions": 0}

        for c in campaigns:
            campaign_id = str(c.get("campaign_id") or "")
            if not campaign_id:
                continue
            c_norm = {
                "id": campaign_id,
                "name": c.get("campaign_name"),
                "status": c.get("status"),
                "type": c.get("type") or c.get("strategy_type"),
                "strategy_type": c.get("strategy_type"),
                "metrika_counter_id": c.get("metrika_counter_id"),
                "goal_ids": c.get("goal_ids") or [],
                "daily_budget": c.get("daily_budget"),
                "stats": c.get("stats") or {},
                "geo": c.get("geo") or [],
                "negative_keywords": c.get("negative_keywords") or [],
            }
            await snapshots.upsert_snapshot(
                account_id=account.id,
                entity_type=SnapshotEntityType.campaign,
                entity_key=campaign_id,
                content_hash=_hash(c_norm),
                raw_snapshot=c,
                normalized_snapshot=c_norm,
                captured_at=now,
            )
            counts["campaigns"] += 1

            for g in c.get("groups", []) or []:
                group_id = str(g.get("group_id") or "")
                if not group_id:
                    continue
                g_norm = {
                    "id": group_id,
                    "campaign_id": campaign_id,
                    "name": g.get("group_name"),
                    "status": g.get("status"),
                    "serving_status": g.get("serving_status"),
                    "autotargeting": g.get("autotargeting"),
                    "negative_keywords": g.get("negative_keywords") or [],
                    "audiences": g.get("audiences") or [],
                }
                await snapshots.upsert_snapshot(
                    account_id=account.id,
                    entity_type=SnapshotEntityType.ad_group,
                    entity_key=group_id,
                    content_hash=_hash(g_norm),
                    raw_snapshot=g,
                    normalized_snapshot=g_norm,
                    captured_at=now,
                )
                counts["groups"] += 1

                for kw in g.get("keywords", []) or []:
                    kw_id = str(kw.get("keyword_id") or "")
                    if not kw_id:
                        continue
                    phrase = kw.get("text")
                    k_norm = {
                        "id": kw_id,
                        "campaign_id": campaign_id,
                        "ad_group_id": group_id,
                        "text": phrase,
                        "phrase": phrase,
                        "status": kw.get("status"),
                        "state": kw.get("status"),
                    }
                    await snapshots.upsert_snapshot(
                        account_id=account.id,
                        entity_type=SnapshotEntityType.keyword,
                        entity_key=kw_id,
                        content_hash=_hash(k_norm),
                        raw_snapshot=kw,
                        normalized_snapshot=k_norm,
                        captured_at=now,
                    )
                    counts["keywords"] += 1

                for ad in g.get("ads", []) or []:
                    ad_id = str(ad.get("ad_id") or "")
                    if not ad_id:
                        continue
                    enriched_sitelinks: list[dict] = []
                    for sl in ad.get("sitelinks") or []:
                        if not isinstance(sl, dict):
                            continue
                        surl = str(sl.get("url") or "")
                        sh = check_map.get(surl) or {}
                        sl2 = dict(sl)
                        sl2["url_health_error"] = bool(
                            sh.get("network_error")
                            or sh.get("ssl_error")
                            or (isinstance(sh.get("status_code"), int) and sh.get("status_code", 0) >= 400)
                        )
                        sl2["url_health"] = sh
                        enriched_sitelinks.append(sl2)

                    main_url = str(ad.get("url") or "")
                    a_norm = {
                        "id": ad_id,
                        "campaign_id": campaign_id,
                        "ad_group_id": group_id,
                        "status": ad.get("status"),
                        "state": ad.get("status"),
                        "serving_status": ad.get("serving_status"),
                        "moderation_status": ad.get("moderation_status"),
                        "moderation_notes": ad.get("moderation_notes"),
                        "type": "TEXT_AD",
                        "title": ad.get("title"),
                        "text": ad.get("text"),
                        "url": main_url,
                        "final_url": main_url,
                        "sitelinks": enriched_sitelinks,
                        "callouts": ad.get("callouts") or [],
                        "display_url": ad.get("display_url"),
                        "contact_info": ad.get("contact_info"),
                        "image": ad.get("image"),
                        "url_health": check_map.get(main_url) or {},
                    }
                    await snapshots.upsert_snapshot(
                        account_id=account.id,
                        entity_type=SnapshotEntityType.ad,
                        entity_key=ad_id,
                        content_hash=_hash(a_norm),
                        raw_snapshot=ad,
                        normalized_snapshot=a_norm,
                        captured_at=now,
                    )
                    counts["ads"] += 1

                    ext_norm = {
                        "id": f"ext:{ad_id}",
                        "campaign_id": campaign_id,
                        "ad_group_id": group_id,
                        "ad_id": ad_id,
                        "sitelinks": enriched_sitelinks,
                        "callouts": ad.get("callouts") or [],
                        "display_url": ad.get("display_url"),
                        "contact_info": ad.get("contact_info"),
                        "image": ad.get("image"),
                    }
                    await snapshots.upsert_snapshot(
                        account_id=account.id,
                        entity_type=SnapshotEntityType.extension,
                        entity_key=f"ext:{ad_id}",
                        content_hash=_hash(ext_norm),
                        raw_snapshot=ext_norm,
                        normalized_snapshot=ext_norm,
                        captured_at=now,
                    )
                    counts["extensions"] += 1

        goals = metrika.get("goals") if isinstance(metrika.get("goals"), list) else []
        counters = metrika.get("counters") if isinstance(metrika.get("counters"), list) else []
        metrika_norm = {"goals": goals, "counters": counters}
        await snapshots.upsert_snapshot(
            account_id=account.id,
            entity_type=SnapshotEntityType.account,
            entity_key="metrika",
            content_hash=_hash(metrika_norm),
            raw_snapshot=metrika,
            normalized_snapshot=metrika_norm,
            captured_at=now,
        )

        await session.commit()
        return {"account_id": str(account.id), "counts": counts, "metrika_goals": len(goals)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("fixture_path", type=Path)
    args = parser.parse_args()
    if not args.fixture_path.is_file():
        print(f"File not found: {args.fixture_path}", file=sys.stderr)
        sys.exit(1)

    import asyncio

    result = asyncio.run(import_fixture(args.fixture_path))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
