"""Seed demo account, credentials, and snapshots for UI/testing."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.core.config import settings  # noqa: E402
from app.models.account_credential import AccountCredential  # noqa: E402
from app.models.ad_account import AdAccount  # noqa: E402
from app.models.entity_snapshot import EntitySnapshot, SnapshotEntityType  # noqa: E402


def _hash_payload(payload: dict) -> str:
    import hashlib
    import json

    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def main() -> None:
    engine = create_engine(settings.database_url_sync, pool_pre_ping=True)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    now = datetime.now(timezone.utc)

    with SessionLocal() as session:
        account = session.execute(select(AdAccount).where(AdAccount.login == "demo_account")).scalar_one_or_none()
        if account is None:
            account = AdAccount(
                external_id=f"demo-{uuid4()}",
                name="Demo Developer ЖК",
                login="demo_account",
                platform="yandex_direct",
                timezone="Europe/Moscow",
                is_active=True,
            )
            session.add(account)
            session.flush()
            print("Created demo ad account")
        else:
            print("Demo ad account already exists")

        credential = (
            session.execute(select(AccountCredential).where(AccountCredential.account_id == account.id))
            .scalars()
            .first()
        )
        if credential is None:
            session.add(
                AccountCredential(
                    account_id=account.id,
                    provider="yandex_direct",
                    access_token_encrypted="demo-token",
                    refresh_token_encrypted=None,
                    token_expires_at=None,
                )
            )
            print("Created demo account credential")

        campaign_payload = {
            "id": "demo-campaign-1",
            "name": "Новостройки Москва",
            "status": "active",
            "strategy_type": "conversion_maximization",
            "stats": {
                "conversions": 12,
                "analysis_period_days": 14,
                "budget_limited_days": 5,
                "avg_hour_of_budget_exhaustion": 13,
            },
        }
        ad_payload = {
            "id": "demo-ad-1",
            "campaign_id": "demo-campaign-1",
            "ad_group_id": "demo-group-1",
            "title": "Квартиры в Москве {{price}}",
            "text": "Сдача в 2024, ипотека 0.1%",
            "status": "active",
            "url": "http://example.com/?utm_source=yandex&utm_source=dup&utm_medium=&utm_campaign=test",
            "sitelinks": [{"url": "https://another-domain.example/flats"}],
            "url_health": {
                "status_code": 404,
                "network_error": "",
                "ssl_error": "",
                "redirect_chain": ["http://example.com", "https://example.com", "http://example.com"],
                "final_url": "http://example.com/final",
            },
        }

        for entity_type, entity_key, payload in [
            (SnapshotEntityType.campaign, "demo-campaign-1", campaign_payload),
            (SnapshotEntityType.ad_group, "demo-group-1", {"id": "demo-group-1", "campaign_id": "demo-campaign-1", "name": "Группа 1", "status": "active"}),
            (SnapshotEntityType.ad, "demo-ad-1", ad_payload),
            (SnapshotEntityType.keyword, "demo-keyword-1", {"id": "demo-keyword-1", "campaign_id": "demo-campaign-1", "ad_group_id": "demo-group-1", "phrase": "купить квартиру", "status": "active"}),
            (SnapshotEntityType.keyword, "demo-keyword-2", {"id": "demo-keyword-2", "campaign_id": "demo-campaign-1", "ad_group_id": "demo-group-1", "phrase": "купить   квартиру!!", "status": "active"}),
        ]:
            exists = (
                session.execute(
                    select(EntitySnapshot).where(
                        EntitySnapshot.account_id == account.id,
                        EntitySnapshot.entity_type == entity_type,
                        EntitySnapshot.entity_key == entity_key,
                    )
                )
                .scalars()
                .first()
            )
            if exists is None:
                session.add(
                    EntitySnapshot(
                        account_id=account.id,
                        entity_type=entity_type,
                        entity_key=entity_key,
                        content_hash=_hash_payload(payload),
                        raw_snapshot=payload,
                        normalized_snapshot=payload,
                        captured_at=now,
                    )
                )
        session.commit()
        print("Demo snapshots are ready")


if __name__ == "__main__":
    main()
