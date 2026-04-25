"""Yandex Direct dynamic URL parameters (macros) — not errors for UTM/placeholder checks.

See https://yandex.ru/support/direct/ru/statistics/url-tags#dynamic
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any

# Lowercase names inside `{...}` (Yandex substitutes these at click time).
_YANDEX_DYNAMIC_INNER_NAMES: frozenset[str] = frozenset(
    {
        "ad_id",
        "banner_id",
        "campaign_id",
        "campaign_name",
        "campaign_name_lat",
        "campaign_type",
        "creative_id",
        "device_type",
        "gbid",
        "keyword",
        "phrase_id",
        "retargeting_id",
        "coef_goal_context_id",
        "match_type",
        "matched_keyword",
        "adtarget_name",
        "adtarget_id",
        "position",
        "position_type",
        "source",
        "source_type",
        "region_name",
        "region_id",
        "yclid",
        "interest_id",
        "interest_name",
        "addphrases",
        "addphrasestext",
        "adds",
        "all_goals",
        # Подстановки «параметр 1/2» в ссылке (XLS/Commander/API), см. справку Директа.
        "param1",
        "param2",
    }
)

_SINGLE_BRACE = re.compile(r"\{([^{}]+)\}")


def yandex_direct_dynamic_inner_names() -> frozenset[str]:
    return _YANDEX_DYNAMIC_INNER_NAMES


def is_yandex_direct_single_brace_placeholder(token: str) -> bool:
    """True for `{keyword}` style tokens listed in Direct dynamic-parameter docs."""
    inner = token.strip()
    if len(inner) < 3 or inner[0] != "{" or inner[-1] != "}":
        return False
    name = inner[1:-1].strip().lower()
    return name in _YANDEX_DYNAMIC_INNER_NAMES


@lru_cache(maxsize=4096)
def _cached_is_known_brace(token: str) -> bool:
    return is_yandex_direct_single_brace_placeholder(token)


def filter_non_yandex_placeholders(placeholders: list[str]) -> list[str]:
    """Keep only placeholders that are not Yandex Direct dynamic `{...}` macros."""
    return [p for p in placeholders if not _cached_is_known_brace(p.strip())]


def normalize_query_value_for_yandex_macros(value: str) -> str:
    """Replace known `{name}` macros so UTM fingerprints treat them as one bucket."""

    def repl(m: re.Match[str]) -> str:
        inner = m.group(1).strip().lower()
        if inner in _YANDEX_DYNAMIC_INNER_NAMES:
            return "{__yndx_dynamic__}"
        return m.group(0)

    return _SINGLE_BRACE.sub(repl, value)


def utm_pairs_with_yandex_macro_normalization(
    pairs: list[tuple[str, str]],
) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for k, v in pairs:
        out.append((k, normalize_query_value_for_yandex_macros(str(v))))
    return out


def metrika_counter_ids_from_campaign(campaign: dict[str, Any]) -> list[str]:
    """Collect Metrika counter ids from snapshot (single field, list, or nested objects)."""
    out: list[str] = []

    def push(val: Any) -> None:
        if val is None:
            return
        s = str(val).strip()
        low = s.lower()
        if not s or low in {"none", "null", "0"}:
            return
        out.append(s)

    mid = campaign.get("metrika_counter_id")
    if isinstance(mid, list):
        for x in mid:
            push(x)
    else:
        push(mid)

    for key in ("metrika_counter_ids", "metrika_counters", "counter_ids", "CounterIds"):
        raw = campaign.get(key)
        if not isinstance(raw, list):
            continue
        for item in raw:
            if isinstance(item, dict):
                push(item.get("Id") or item.get("id") or item.get("CounterId") or item.get("counter_id"))
            else:
                push(item)
    # Dedupe preserving order
    seen: set[str] = set()
    uniq: list[str] = []
    for x in out:
        if x not in seen:
            seen.add(x)
            uniq.append(x)
    return uniq
