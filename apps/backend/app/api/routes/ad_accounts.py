import base64
import hashlib
import hmac
import json
import asyncio
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus, urlsplit, urlunsplit
from secrets import token_urlsafe
from collections import defaultdict
from typing import Annotated, Any
from uuid import UUID

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, RequireAdmin, get_db
from app.core.config import settings
from app.repositories.account_credential import AccountCredentialRepository
from app.repositories.ad_account import AdAccountRepository
from app.repositories.entity_snapshot import EntitySnapshotRepository
from app.schemas.reporting import AdAccountOut, AdAccountUpdateRequest, CampaignOut, DirectApiUnitsOut
from app.models.entity_snapshot import SnapshotEntityType

router = APIRouter(prefix="/ad-accounts", tags=["ad-accounts"])
STATE_TTL_MINUTES = 15
HTTP_RETRY_ATTEMPTS = 3
HTTP_RETRY_BACKOFF_SECONDS = 0.7


def _normalize_region_ids_for_snapshot(raw: Any) -> list[int]:
    """Yandex Direct RegionIds list or ``{\"Items\": [...]}`` wrapper → sorted unique ints."""
    if raw is None:
        return []
    if isinstance(raw, dict) and "Items" in raw:
        raw = raw["Items"]
    if not isinstance(raw, list):
        return []
    out: list[int] = []
    for x in raw:
        try:
            out.append(int(x))
        except (TypeError, ValueError):
            continue
    return sorted(set(out))


def _normalize_counter_ids_for_snapshot(raw: Any) -> list[str]:
    """Yandex Direct CounterIds list or wrapped payload -> sorted unique string ids."""
    if raw is None:
        return []
    if isinstance(raw, dict):
        if "Items" in raw:
            raw = raw.get("Items")
        elif "CounterIds" in raw:
            raw = raw.get("CounterIds")
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    for x in raw:
        s = str(x).strip()
        if not s or s.lower() in {"none", "null", "0"}:
            continue
        out.append(s)
    return sorted(set(out))


def _normalize_tracking_params(raw: Any) -> str | None:
    """Tracking params from Direct API as trimmed query string."""
    if raw is None:
        return None
    s = str(raw).strip()
    return s or None


def _campaign_type_payload(item: dict[str, Any]) -> dict[str, Any]:
    for key in ("TextCampaign", "UnifiedCampaign", "SmartCampaign", "DynamicTextCampaign", "MobileAppCampaign"):
        block = item.get(key)
        if isinstance(block, dict):
            return block
    return {}


def _campaign_counter_ids(item: dict[str, Any]) -> list[str]:
    direct = _normalize_counter_ids_for_snapshot(item.get("CounterIds"))
    if direct:
        return direct
    block = _campaign_type_payload(item)
    return _normalize_counter_ids_for_snapshot(block.get("CounterIds"))


def _campaign_tracking_params(item: dict[str, Any]) -> str | None:
    direct = _normalize_tracking_params(item.get("TrackingParams"))
    if direct:
        return direct
    block = _campaign_type_payload(item)
    return _normalize_tracking_params(block.get("TrackingParams"))


def _collect_goal_ids_from_payload(node: Any, out: list[str]) -> None:
    if isinstance(node, dict):
        for k, v in node.items():
            lk = str(k).lower()
            if lk in {"goalid", "goal_id", "optimizegoalid", "optimize_goal_id"}:
                if isinstance(v, list):
                    for x in v:
                        sx = str(x).strip()
                        if sx and sx not in {"0", "None", "null"}:
                            out.append(sx)
                else:
                    sx = str(v).strip()
                    if sx and sx not in {"0", "None", "null"}:
                        out.append(sx)
            _collect_goal_ids_from_payload(v, out)
    elif isinstance(node, list):
        for item in node:
            _collect_goal_ids_from_payload(item, out)


def _campaign_goal_ids(item: dict[str, Any]) -> list[str]:
    out: list[str] = []
    # 1) explicit top-level list if present
    top = item.get("GoalIds")
    if isinstance(top, list):
        for x in top:
            sx = str(x).strip()
            if sx and sx not in {"0", "None", "null"}:
                out.append(sx)
    # 2) scan full payload + typed payload for nested GoalId/OptimizeGoalId
    _collect_goal_ids_from_payload(item, out)
    _collect_goal_ids_from_payload(_campaign_type_payload(item), out)
    seen: set[str] = set()
    uniq: list[str] = []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq


def _parse_units_header(raw_units: str | None) -> tuple[int | None, int | None, int | None]:
    if not raw_units:
        return None, None, None
    parts = [p.strip() for p in raw_units.split("/")]
    if len(parts) != 3:
        return None, None, None
    try:
        return int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return None, None, None


@router.get("", response_model=list[AdAccountOut])
async def list_ad_accounts(
    _user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[AdAccountOut]:
    repo = AdAccountRepository(session)
    rows = await repo.list_with_last_audit()
    return [
        AdAccountOut(
            id=row.id,
            external_id=row.external_id,
            name=row.name,
            login=row.login,
            platform=row.platform,
            timezone=row.timezone,
            is_active=row.is_active,
            last_audit_at=last_audit_at,
        )
        for row, last_audit_at in rows
    ]


@router.get("/{account_id}/campaigns", response_model=list[CampaignOut])
async def list_account_campaigns(
    account_id: UUID,
    _user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[CampaignOut]:
    snapshots = EntitySnapshotRepository(session)
    campaigns = await snapshots.list_latest_campaigns(account_id=account_id)
    return [
        CampaignOut(
            id=str(item.get("id")),
            name=item.get("name"),
            status=item.get("status"),
        )
        for item in campaigns
        if item.get("id") is not None
    ]


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ad_account(
    account_id: UUID,
    _admin: RequireAdmin,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    repo = AdAccountRepository(session)
    account = await repo.get_by_id(account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ad account not found")
    await repo.delete(account)
    await session.commit()


@router.put("/{account_id}", response_model=AdAccountOut)
async def update_ad_account(
    account_id: UUID,
    body: AdAccountUpdateRequest,
    _admin: RequireAdmin,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AdAccountOut:
    repo = AdAccountRepository(session)
    account = await repo.get_by_id(account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ad account not found")
    account.name = body.name.strip()
    await session.commit()
    return AdAccountOut(
        id=account.id,
        external_id=account.external_id,
        name=account.name,
        login=account.login,
        platform=account.platform,
        timezone=account.timezone,
        is_active=account.is_active,
        last_audit_at=None,
    )


@router.get("/oauth/start")
async def start_direct_oauth(
    _admin: RequireAdmin,
    ui_redirect: Annotated[str | None, Query()] = None,
    project_name: Annotated[str | None, Query()] = None,
) -> dict[str, str]:
    client_id = settings.yandex_oauth_client_id.strip()
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="YANDEX_OAUTH_CLIENT_ID is empty. Set OAuth client id to enable flow start.",
        )
    yandex_redirect_uri = settings.yandex_oauth_redirect_uri.strip()
    if not yandex_redirect_uri:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing redirect uri")
    ui_redirect_target = ui_redirect or settings.yandex_oauth_ui_return_url()
    state_payload = {
        "nonce": token_urlsafe(10),
        "exp": int((datetime.now(timezone.utc) + timedelta(minutes=STATE_TTL_MINUTES)).timestamp()),
        "project_name": (project_name or "").strip()[:255],
        "ui_redirect": ui_redirect_target,
    }
    state = _sign_state(state_payload)
    auth_url = (
        "https://oauth.yandex.ru/authorize"
        f"?response_type=code&client_id={client_id}&state={state}&redirect_uri={yandex_redirect_uri}"
    )
    return {"auth_url": auth_url, "state": state}


@router.get("/oauth/callback")
async def oauth_callback(
    session: Annotated[AsyncSession, Depends(get_db)],
    code: Annotated[str | None, Query()] = None,
    state: Annotated[str | None, Query()] = None,
    error: Annotated[str | None, Query()] = None,
    error_description: Annotated[str | None, Query()] = None,
) -> RedirectResponse:
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"OAuth error: {error} ({error_description or 'no description'})",
        )
    if not code or not state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing code/state")
    payload = _verify_state(state)
    if payload.get("exp", 0) < int(datetime.now(timezone.utc).timestamp()):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="OAuth state expired")

    client_id = settings.yandex_oauth_client_id.strip()
    client_secret = settings.yandex_oauth_client_secret.strip()
    redirect_uri = settings.yandex_oauth_redirect_uri.strip()
    if not client_id or not client_secret or not redirect_uri:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="YANDEX_OAUTH_CLIENT_ID/SECRET/REDIRECT_URI are required",
        )

    token_data = await _exchange_code_for_token(
        code=code,
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
    )

    profile = await _fetch_yandex_profile(access_token=token_data.get("access_token", ""))
    login_from_profile = str(profile.get("login") or "").strip()
    uid = str(profile.get("id") or token_data.get("uid") or token_data.get("user_id") or token_data.get("x_uid") or "")
    if not uid:
        uid = hashlib.sha256((token_data.get("access_token") or "").encode("utf-8")).hexdigest()[:16]
    login = await _resolve_direct_login(access_token=token_data.get("access_token", ""), fallback_login=login_from_profile)
    login = login or f"direct_{uid}"
    project_name = payload.get("project_name") or f"Yandex Direct {login}"
    external_id = f"ya-{uid}"

    accounts = AdAccountRepository(session)
    creds = AccountCredentialRepository(session)

    account = await accounts.get_by_external_id(external_id)
    if account is None:
        login_candidate = login
        existing_login = await accounts.get_by_login(login_candidate)
        if existing_login is not None:
            login_candidate = f"{login}_{token_urlsafe(4)}"
        account = await accounts.create(
            external_id=external_id,
            name=project_name,
            login=login_candidate,
        )
    else:
        account.name = project_name
        if account.login != login:
            duplicate = await accounts.get_by_login(login)
            if duplicate is None or duplicate.id == account.id:
                account.login = login
        account.is_active = True

    expires_in = token_data.get("expires_in")
    token_expires_at = None
    if isinstance(expires_in, int):
        token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    await creds.upsert(
        account_id=account.id,
        access_token=token_data.get("access_token", ""),
        refresh_token=token_data.get("refresh_token"),
        token_expires_at=token_expires_at,
    )
    await session.commit()
    ui_redirect = str(payload.get("ui_redirect") or settings.yandex_oauth_ui_return_url())
    project_redirect = _to_project_redirect(ui_redirect=ui_redirect, account_id=str(account.id))
    sep = "&" if "?" in project_redirect else "?"
    return RedirectResponse(
        url=f"{project_redirect}{sep}oauth=success&account_id={account.id}&login={quote_plus(account.login)}",
        status_code=status.HTTP_302_FOUND,
    )


@router.post("/{account_id}/sync-campaigns")
async def sync_account_campaigns(
    account_id: UUID,
    _user: CurrentUser,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, int]:
    accounts = AdAccountRepository(session)
    account = await accounts.get_by_id(account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ad account not found")

    creds = AccountCredentialRepository(session)
    credential = await creds.get_by_account_id(account_id)
    if credential is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No OAuth credential for account")

    # Avoid extra Direct API /clients calls on every sync.
    # Login refresh is needed mostly for temporary fallback logins.
    access_token = creds.get_access_token(credential)
    if account.login.startswith("direct_"):
        refreshed_login = await _resolve_direct_login(
            access_token=access_token,
            fallback_login=account.login,
        )
        if refreshed_login and refreshed_login != account.login:
            duplicate = await accounts.get_by_login(refreshed_login)
            if duplicate is None or duplicate.id == account.id:
                account.login = refreshed_login

    campaigns = await _fetch_direct_campaigns(
        access_token=access_token,
        client_login=account.login,
    )
    campaign_ids = [int(item.get("Id")) for item in campaigns if item.get("Id") is not None]
    ad_groups = await _fetch_direct_ad_groups(
        access_token=access_token,
        client_login=account.login,
        campaign_ids=campaign_ids,
    )
    ad_group_ids = [int(item.get("Id")) for item in ad_groups if item.get("Id") is not None]
    audience_targets = await _fetch_direct_audience_targets(
        access_token=access_token,
        client_login=account.login,
        ad_group_ids=ad_group_ids,
    )
    ads = await _fetch_direct_ads(
        access_token=access_token,
        client_login=account.login,
        campaign_ids=campaign_ids,
    )
    keywords = await _fetch_direct_keywords(
        access_token=access_token,
        client_login=account.login,
        campaign_ids=campaign_ids,
    )
    repo = EntitySnapshotRepository(session)
    now = datetime.now(timezone.utc)
    upserted = 0
    campaign_region_ids: dict[str, set[int]] = defaultdict(set)
    retargeting_by_group: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in audience_targets:
        gid = str(item.get("AdGroupId") or "")
        if not gid:
            continue
        retargeting_by_group[gid].append(
            {
                "id": str(item.get("Id") or ""),
                "campaign_id": str(item.get("CampaignId") or ""),
                "retargeting_list_id": item.get("RetargetingListId"),
                "state": item.get("State"),
            }
        )

    for item in ad_groups:
        group_id = str(item.get("Id") or "")
        if not group_id:
            continue
        campaign_id_str = str(item.get("CampaignId") or "")
        region_ids = _normalize_region_ids_for_snapshot(item.get("RegionIds"))
        campaign_region_ids[campaign_id_str].update(region_ids)
        normalized = {
            "id": group_id,
            "campaign_id": campaign_id_str,
            "name": item.get("Name"),
            "status": item.get("Status"),
            "serving_status": item.get("ServingStatus"),
            "region_ids": region_ids,
            "retargeting_lists": retargeting_by_group.get(group_id, []),
            "tracking_params": _normalize_tracking_params(item.get("TrackingParams")),
            "tracking_template": _normalize_tracking_params(item.get("TrackingParams")),
            "tracking_url": _normalize_tracking_params(item.get("TrackingParams")),
        }
        content_hash = hashlib.sha256(
            json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        await repo.upsert_snapshot(
            account_id=account_id,
            entity_type=SnapshotEntityType.ad_group,
            entity_key=group_id,
            content_hash=content_hash,
            raw_snapshot=item,
            normalized_snapshot=normalized,
            captured_at=now,
        )
    for item in campaigns:
        campaign_id = str(item.get("Id") or item.get("id") or "")
        if not campaign_id:
            continue
        merged_regions = sorted(campaign_region_ids.get(campaign_id, set()))
        normalized = {
            "id": campaign_id,
            "name": item.get("Name"),
            "status": item.get("State"),
            "type": item.get("Type"),
            "counter_ids": _campaign_counter_ids(item),
            "CounterIds": _campaign_counter_ids(item),
            "metrika_counter_ids": _campaign_counter_ids(item),
            "tracking_params": _campaign_tracking_params(item),
            "tracking_template": _campaign_tracking_params(item),
            "tracking_url": _campaign_tracking_params(item),
            "goal_ids": _campaign_goal_ids(item),
            "region_ids": merged_regions,
        }
        content_hash = hashlib.sha256(
            json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        await repo.upsert_snapshot(
            account_id=account_id,
            entity_type=SnapshotEntityType.campaign,
            entity_key=campaign_id,
            content_hash=content_hash,
            raw_snapshot=item,
            normalized_snapshot=normalized,
            captured_at=now,
        )
        upserted += 1
    for item in ads:
        ad_id = str(item.get("Id") or "")
        if not ad_id:
            continue
        text_ad = item.get("TextAd") if isinstance(item.get("TextAd"), dict) else {}
        normalized = {
            "id": ad_id,
            "campaign_id": str(item.get("CampaignId") or ""),
            "ad_group_id": str(item.get("AdGroupId") or ""),
            "status": item.get("Status"),
            "state": item.get("State"),
            "type": item.get("Type"),
            "title": text_ad.get("Title"),
            "text": text_ad.get("Text"),
            "url": text_ad.get("Href"),
            "final_url": text_ad.get("Href"),
        }
        content_hash = hashlib.sha256(
            json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        await repo.upsert_snapshot(
            account_id=account_id,
            entity_type=SnapshotEntityType.ad,
            entity_key=ad_id,
            content_hash=content_hash,
            raw_snapshot=item,
            normalized_snapshot=normalized,
            captured_at=now,
        )
    for item in keywords:
        keyword_id = str(item.get("Id") or "")
        if not keyword_id:
            continue
        normalized = {
            "id": keyword_id,
            "campaign_id": str(item.get("CampaignId") or ""),
            "ad_group_id": str(item.get("AdGroupId") or ""),
            "text": item.get("Keyword"),
            "phrase": item.get("Keyword"),
            "status": item.get("Status"),
            "state": item.get("State"),
        }
        content_hash = hashlib.sha256(
            json.dumps(normalized, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).hexdigest()
        await repo.upsert_snapshot(
            account_id=account_id,
            entity_type=SnapshotEntityType.keyword,
            entity_key=keyword_id,
            content_hash=content_hash,
            raw_snapshot=item,
            normalized_snapshot=normalized,
            captured_at=now,
        )
    await session.commit()
    return {"synced_campaigns": upserted}


@router.get("/{account_id}/direct-api-units", response_model=DirectApiUnitsOut)
async def get_direct_api_units(
    account_id: UUID,
    _admin: RequireAdmin,
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DirectApiUnitsOut:
    accounts = AdAccountRepository(session)
    account = await accounts.get_by_id(account_id)
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ad account not found")

    creds = AccountCredentialRepository(session)
    credential = await creds.get_by_account_id(account_id)
    if credential is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No OAuth credential for account")

    access_token = creds.get_access_token(credential)
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept-Language": "ru",
        "Content-Type": "application/json; charset=utf-8",
    }
    if account.login:
        headers["Client-Login"] = account.login

    body = {
        "method": "get",
        "params": {
            "SelectionCriteria": {},
            "FieldNames": ["Id"],
            "Page": {"Limit": 1, "Offset": 0},
        },
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await _post_with_retry(
            client=client,
            url=settings.yandex_direct_api_url.rstrip("/") + "/campaigns",
            headers=headers,
            json=body,
        )
    if resp.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Yandex Direct units check failed: {resp.status_code} {resp.text}",
        )
    payload = resp.json()
    if "error" in payload:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Yandex Direct error: {payload['error']}")

    raw_units = resp.headers.get("Units")
    spent, remaining, daily_limit = _parse_units_header(raw_units)
    return DirectApiUnitsOut(
        account_id=account.id,
        account_login=account.login,
        spent=spent,
        remaining=remaining,
        daily_limit=daily_limit,
        units_used_login=resp.headers.get("Units-Used-Login"),
        units_header_raw=raw_units,
    )


def _state_secret() -> bytes:
    return settings.jwt_secret_key.encode("utf-8")


def _sign_state(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    sig = hmac.new(_state_secret(), raw, hashlib.sha256).digest()
    body = base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")
    sign = base64.urlsafe_b64encode(sig).decode("utf-8").rstrip("=")
    return f"{body}.{sign}"


def _verify_state(state: str) -> dict:
    try:
        body, sign = state.split(".", 1)
        raw = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
        expected = hmac.new(_state_secret(), raw, hashlib.sha256).digest()
        actual = base64.urlsafe_b64decode(sign + "=" * (-len(sign) % 4))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state") from exc
    if not hmac.compare_digest(expected, actual):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid OAuth state signature")
    return json.loads(raw.decode("utf-8"))


async def _exchange_code_for_token(
    *,
    code: str,
    client_id: str,
    client_secret: str,
    redirect_uri: str,
) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await _post_with_retry(
            client=client,
            url="https://oauth.yandex.ru/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
    if resp.status_code >= 400:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Token exchange failed: {resp.status_code} {resp.text}",
        )
    payload = resp.json()
    if not payload.get("access_token"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Token exchange returned empty access_token")
    return payload


async def _fetch_yandex_profile(*, access_token: str) -> dict:
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await _get_with_retry(
            client=client,
            url="https://login.yandex.ru/info",
            params={"format": "json"},
            headers={"Authorization": f"OAuth {access_token}"},
        )
    if resp.status_code >= 400:
        return {}
    return resp.json()


async def _fetch_direct_campaigns(*, access_token: str, client_login: str) -> list[dict]:
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept-Language": "ru",
        "Content-Type": "application/json; charset=utf-8",
    }
    if client_login:
        headers["Client-Login"] = client_login
    merged: dict[str, dict] = {}
    async with httpx.AsyncClient(timeout=25) as client:
        # Pass 1: always fetch base campaign rows (stable across types).
        base_body = {
            "method": "get",
            "params": {
                "SelectionCriteria": {},
                "FieldNames": ["Id", "Name", "State", "Type"],
            },
        }
        resp = await _post_with_retry(
            client=client,
            url=settings.yandex_direct_api_url.rstrip("/") + "/campaigns",
            headers=headers,
            json=base_body,
        )
        if resp.status_code >= 400:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Yandex Direct campaigns sync failed: {resp.status_code} {resp.text}",
            )
        payload = resp.json()
        if "error" in payload:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Yandex Direct error: {payload['error']}")
        for row in payload.get("result", {}).get("Campaigns", []):
            cid = str(row.get("Id") or "")
            if cid:
                merged[cid] = row

        # Pass 2: enrich by campaign type (optional, best-effort).
        by_type: dict[str, list[int]] = defaultdict(list)
        for row in merged.values():
            ctype = str(row.get("Type") or "")
            cid_raw = row.get("Id")
            if not ctype or cid_raw is None:
                continue
            try:
                by_type[ctype].append(int(cid_raw))
            except (TypeError, ValueError):
                continue

        type_enrichment = {
            "TEXT_CAMPAIGN": ("TextCampaignFieldNames", ["CounterIds", "TrackingParams", "BiddingStrategy", "PriorityGoals"]),
            "UNIFIED_CAMPAIGN": ("UnifiedCampaignFieldNames", ["CounterIds", "TrackingParams", "BiddingStrategy", "PriorityGoals"]),
            "SMART_CAMPAIGN": ("SmartCampaignFieldNames", ["CounterIds", "TrackingParams", "BiddingStrategy", "PriorityGoals"]),
            "DYNAMIC_TEXT_CAMPAIGN": (
                "DynamicTextCampaignFieldNames",
                ["CounterIds", "TrackingParams", "BiddingStrategy", "PriorityGoals"],
            ),
            "MOBILE_APP_CAMPAIGN": (
                "MobileAppCampaignFieldNames",
                ["CounterIds", "TrackingParams", "BiddingStrategy", "PriorityGoals"],
            ),
        }
        for ctype, (field_key, field_values) in type_enrichment.items():
            ids = by_type.get(ctype) or []
            if not ids:
                continue
            for i in range(0, len(ids), 10):
                chunk = ids[i : i + 10]
                enrich_body = {
                    "method": "get",
                    "params": {
                        "SelectionCriteria": {"Ids": chunk},
                        "FieldNames": ["Id", "Name", "State", "Type"],
                        field_key: field_values,
                    },
                }
                try:
                    resp = await _post_with_retry(
                        client=client,
                        url=settings.yandex_direct_api_url.rstrip("/") + "/campaigns",
                        headers=headers,
                        json=enrich_body,
                    )
                    if resp.status_code >= 400:
                        continue
                    payload = resp.json()
                    if "error" in payload:
                        continue
                    for row in payload.get("result", {}).get("Campaigns", []):
                        cid = str(row.get("Id") or "")
                        if cid and cid in merged:
                            merged[cid].update(row)
                except Exception:
                    continue
    return list(merged.values())


async def _resolve_direct_login(*, access_token: str, fallback_login: str) -> str:
    body = {
        "method": "get",
        "params": {
            "FieldNames": ["Login", "ClientId"],
        },
    }
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept-Language": "ru",
        "Content-Type": "application/json; charset=utf-8",
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await _post_with_retry(
                client=client,
                url=settings.yandex_direct_api_url.rstrip("/") + "/clients",
                headers=headers,
                json=body,
            )
        if resp.status_code >= 400:
            return fallback_login
        payload = resp.json()
        rows = payload.get("result", {}).get("Clients", [])
        if rows and rows[0].get("Login"):
            return str(rows[0]["Login"])
    except Exception:
        return fallback_login
    return fallback_login


async def _fetch_direct_ad_groups(*, access_token: str, client_login: str, campaign_ids: list[int]) -> list[dict]:
    if not campaign_ids:
        return []
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept-Language": "ru",
        "Content-Type": "application/json; charset=utf-8",
    }
    if client_login:
        headers["Client-Login"] = client_login
    rows: list[dict] = []
    async with httpx.AsyncClient(timeout=25) as client:
        for i in range(0, len(campaign_ids), 10):
            chunk = campaign_ids[i : i + 10]
            payload: dict[str, Any] | None = None
            for field_names in (
                ["Id", "CampaignId", "Name", "Status", "ServingStatus", "RegionIds", "TrackingParams"],
                ["Id", "CampaignId", "Name", "Status", "ServingStatus", "RegionIds"],
            ):
                body = {
                    "method": "get",
                    "params": {
                        "SelectionCriteria": {"CampaignIds": chunk},
                        "FieldNames": field_names,
                    },
                }
                resp = await _post_with_retry(
                    client=client,
                    url=settings.yandex_direct_api_url.rstrip("/") + "/adgroups",
                    headers=headers,
                    json=body,
                )
                if resp.status_code >= 400:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Yandex Direct adgroups failed: {resp.status_code} {resp.text}",
                    )
                payload = resp.json()
                if "error" not in payload:
                    break
                error = payload["error"]
                detail = str(error.get("error_detail") or "")
                if error.get("error_code") == 8000 and "неверное значение перечисления" in detail.lower():
                    continue
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Yandex Direct error: {error}")
            if payload is None:
                continue
            if "error" in payload:
                continue
            rows.extend(payload.get("result", {}).get("AdGroups", []))
    return rows


async def _fetch_direct_audience_targets(*, access_token: str, client_login: str, ad_group_ids: list[int]) -> list[dict]:
    """
    Fetch ad group audience bindings (retargeting/segments).
    Gracefully fallback to [] if this service isn't available for the account.
    """
    if not ad_group_ids:
        return []
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept-Language": "ru",
        "Content-Type": "application/json; charset=utf-8",
    }
    if client_login:
        headers["Client-Login"] = client_login
    rows: list[dict] = []
    async with httpx.AsyncClient(timeout=25) as client:
        for i in range(0, len(ad_group_ids), 200):
            chunk = ad_group_ids[i : i + 200]
            body = {
                "method": "get",
                "params": {
                    "SelectionCriteria": {"AdGroupIds": chunk},
                    "FieldNames": [
                        "Id",
                        "AdGroupId",
                        "CampaignId",
                        "RetargetingListId",
                        "State",
                    ],
                },
            }
            try:
                resp = await _post_with_retry(
                    client=client,
                    url=settings.yandex_direct_api_url.rstrip("/") + "/audiencetargets",
                    headers=headers,
                    json=body,
                )
                if resp.status_code >= 400:
                    return []
                payload = resp.json()
                if "error" in payload:
                    return []
                rows.extend(payload.get("result", {}).get("AudienceTargets", []))
            except Exception:
                return []
    return rows


async def _fetch_direct_ads(*, access_token: str, client_login: str, campaign_ids: list[int]) -> list[dict]:
    if not campaign_ids:
        return []
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept-Language": "ru",
        "Content-Type": "application/json; charset=utf-8",
    }
    if client_login:
        headers["Client-Login"] = client_login
    rows: list[dict] = []
    async with httpx.AsyncClient(timeout=25) as client:
        for i in range(0, len(campaign_ids), 10):
            chunk = campaign_ids[i : i + 10]
            body = {
                "method": "get",
                "params": {
                    "SelectionCriteria": {"CampaignIds": chunk},
                    "FieldNames": ["Id", "CampaignId", "AdGroupId", "State", "Status", "Type"],
                    "TextAdFieldNames": ["Title", "Title2", "Text", "Href", "Mobile"],
                },
            }
            resp = await _post_with_retry(
                client=client,
                url=settings.yandex_direct_api_url.rstrip("/") + "/ads",
                headers=headers,
                json=body,
            )
            if resp.status_code >= 400:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Yandex Direct ads failed: {resp.status_code} {resp.text}")
            payload = resp.json()
            if "error" in payload:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Yandex Direct error: {payload['error']}")
            rows.extend(payload.get("result", {}).get("Ads", []))
    return rows


async def _fetch_direct_keywords(*, access_token: str, client_login: str, campaign_ids: list[int]) -> list[dict]:
    if not campaign_ids:
        return []
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept-Language": "ru",
        "Content-Type": "application/json; charset=utf-8",
    }
    if client_login:
        headers["Client-Login"] = client_login
    rows: list[dict] = []
    async with httpx.AsyncClient(timeout=25) as client:
        for i in range(0, len(campaign_ids), 10):
            chunk = campaign_ids[i : i + 10]
            body = {
                "method": "get",
                "params": {
                    "SelectionCriteria": {"CampaignIds": chunk},
                    "FieldNames": ["Id", "CampaignId", "AdGroupId", "Keyword", "State", "Status"],
                },
            }
            resp = await _post_with_retry(
                client=client,
                url=settings.yandex_direct_api_url.rstrip("/") + "/keywords",
                headers=headers,
                json=body,
            )
            if resp.status_code >= 400:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=f"Yandex Direct keywords failed: {resp.status_code} {resp.text}"
                )
            payload = resp.json()
            if "error" in payload:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Yandex Direct error: {payload['error']}")
            rows.extend(payload.get("result", {}).get("Keywords", []))
    return rows


def _to_project_redirect(*, ui_redirect: str, account_id: str) -> str:
    parsed = urlsplit(ui_redirect)
    path = parsed.path
    if "/settings" in path:
        path = path.replace("/settings", f"/projects/{account_id}")
    elif path.rstrip("/").endswith("/dashboard"):
        path = path.rstrip("/") + f"/projects/{account_id}"
    else:
        path = path.rstrip("/") + f"/projects/{account_id}"
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


async def _post_with_retry(
    *,
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str] | None = None,
    json: dict | None = None,
    data: dict | None = None,
) -> httpx.Response:
    last_exc: Exception | None = None
    for attempt in range(1, HTTP_RETRY_ATTEMPTS + 1):
        try:
            response = await client.post(url, headers=headers, json=json, data=data)
            if response.status_code >= 500 and attempt < HTTP_RETRY_ATTEMPTS:
                await asyncio.sleep(HTTP_RETRY_BACKOFF_SECONDS * attempt)
                continue
            return response
        except httpx.HTTPError as exc:
            last_exc = exc
            if attempt == HTTP_RETRY_ATTEMPTS:
                raise
            await asyncio.sleep(HTTP_RETRY_BACKOFF_SECONDS * attempt)
    raise RuntimeError("Unexpected retry loop termination") from last_exc


async def _get_with_retry(
    *,
    client: httpx.AsyncClient,
    url: str,
    headers: dict[str, str] | None = None,
    params: dict[str, str] | None = None,
) -> httpx.Response:
    last_exc: Exception | None = None
    for attempt in range(1, HTTP_RETRY_ATTEMPTS + 1):
        try:
            response = await client.get(url, headers=headers, params=params)
            if response.status_code >= 500 and attempt < HTTP_RETRY_ATTEMPTS:
                await asyncio.sleep(HTTP_RETRY_BACKOFF_SECONDS * attempt)
                continue
            return response
        except httpx.HTTPError as exc:
            last_exc = exc
            if attempt == HTTP_RETRY_ATTEMPTS:
                raise
            await asyncio.sleep(HTTP_RETRY_BACKOFF_SECONDS * attempt)
    raise RuntimeError("Unexpected retry loop termination") from last_exc
