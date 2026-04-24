from __future__ import annotations

import json
from typing import Any


def canonicalize_for_fingerprint(value: Any) -> Any:
    """Stabilize nested evidence payloads so equal facts keep same fingerprint."""
    if isinstance(value, dict):
        return {k: canonicalize_for_fingerprint(v) for k, v in sorted(value.items(), key=lambda kv: kv[0])}
    if isinstance(value, list):
        normalized = [canonicalize_for_fingerprint(v) for v in value]
        return sorted(normalized, key=lambda v: json.dumps(v, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    return value


def evidence_signature(evidence: dict) -> str:
    stable = canonicalize_for_fingerprint(evidence)
    return json.dumps(stable, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
