#!/usr/bin/env python3
"""Загрузить rule-catalog.json в API и активировать каталог (нужен Bearer-токен админа).

Альтернатива без консоли: в веб-интерфейсе войти под админом → «Настройки» → блок
«Каталог правил» → «Опубликовать встроенный каталог» (тот же JSON, что в образе бэкенда).

Пример:
  export API_BASE_URL="https://example.ru/YaDirect-analytics/api/v1"
  export ADMIN_ACCESS_TOKEN="eyJ..."
  python scripts/upload_rule_catalog_api.py

Если версия из JSON уже есть в БД (409), скрипт без --catalog-version сам поднимает patch
(1.0.2 → 1.0.3), сверяясь с активным каталогом. Явная версия:

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

from app.services.rule_catalog_bundle import (
    bump_semver_patch,
    convert_frontend_catalog_to_api_payload,
    resolve_bundled_rule_catalog_path,
)


def _rule_catalog_path() -> Path:
    return resolve_bundled_rule_catalog_path()


def _convert_payload(raw: dict, catalog_version: str | None) -> dict:
    return convert_frontend_catalog_to_api_payload(raw, catalog_version)


def _request_json(method: str, url: str, token: str, body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = Request(url, data=data, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    if body is not None:
        req.add_header("Content-Type", "application/json; charset=utf-8")
    with urlopen(req, timeout=120) as resp:
        payload = resp.read().decode("utf-8")
        return json.loads(payload) if payload else {}


def _active_catalog_version(base: str, token: str) -> str | None:
    url = f"{base}/rule-catalogs/active?platform=yandex_direct"
    try:
        req = Request(url, method="GET")
        req.add_header("Authorization", f"Bearer {token}")
        with urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            v = data.get("version")
            return str(v).strip() if v else None
    except OSError:
        return None


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

    if args.dry_run:
        body = _convert_payload(raw, args.catalog_version)
        print(json.dumps(body, ensure_ascii=False, indent=2))
        return

    upload_url = f"{base}/rule-catalogs"
    if args.catalog_version:
        versions_to_try = [args.catalog_version]
    else:
        file_ver = str(raw.get("catalog_version") or "1.0.0")
        active_ver = _active_catalog_version(base, token)
        ver = file_ver
        if active_ver and ver == active_ver:
            ver = bump_semver_patch(ver)
        versions_to_try = []
        cur = ver
        for _ in range(48):
            versions_to_try.append(cur)
            cur = bump_semver_patch(cur)

    created: dict | None = None
    used_version: str | None = None
    for ver_try in versions_to_try:
        body = _convert_payload(raw, ver_try)
        try:
            created = _request_json("POST", upload_url, token, body)
            used_version = ver_try
            break
        except HTTPError as exc:
            err = exc.read().decode("utf-8", errors="replace")
            if exc.code == 409 and not args.catalog_version:
                continue
            print(f"POST {upload_url} failed: {exc.code}\n{err}", file=sys.stderr)
            if exc.code == 409:
                print("Hint: pass --catalog-version with a new value (e.g. 1.0.1)", file=sys.stderr)
            sys.exit(1)

    if not created:
        print("Could not upload catalog: version conflict after retries", file=sys.stderr)
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

    print(
        json.dumps(
            {"catalog_version_used": used_version, "uploaded": created, "activated": active},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
