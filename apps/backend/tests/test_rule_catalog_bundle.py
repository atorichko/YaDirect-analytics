from __future__ import annotations

import json

from app.schemas.rule_catalog import CatalogUploadRequest
from app.services.rule_catalog_bundle import (
    bump_semver_patch,
    convert_frontend_catalog_to_api_payload,
    resolve_bundled_rule_catalog_path,
)


def test_bump_semver_patch() -> None:
    assert bump_semver_patch("1.0.3") == "1.0.4"
    assert bump_semver_patch("1.2") == "1.2.1"


def test_resolve_bundled_rule_catalog_path_exists() -> None:
    p = resolve_bundled_rule_catalog_path()
    assert p.is_file()


def test_convert_catalog_roundtrip() -> None:
    path = resolve_bundled_rule_catalog_path()
    raw = json.loads(path.read_text(encoding="utf-8"))
    body = convert_frontend_catalog_to_api_payload(raw, None)
    payload = CatalogUploadRequest.model_validate(body)
    assert payload.catalog_version
    assert payload.rules
