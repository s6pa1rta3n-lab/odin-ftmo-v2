"""Asset-class classification from the broker's symbol specification.

The class only selects the default commission model (``pct`` for crypto);
it is never used to guess a spec value. Priority: ``AUTOEXEC_ASSET_CLASS_<SYMBOL>``
override, else keywords in the MT5 group ``path`` the broker reports
(e.g. ``Crypto\\BTCUSD``, ``Forex\\Majors\\EURUSD``, ``Indices\\US100.cash``,
``Metals\\XAUUSD``). Unknown -> None (no default model; explicit env needed).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

_PATH_KEYWORDS = (
    ("crypto", "crypto"),
    ("forex", "forex"),
    ("currenc", "forex"),
    ("fx", "forex"),
    ("indic", "index"),
    ("index", "index"),
    ("metal", "metals"),
    ("gold", "metals"),
    ("silver", "metals"),
)


def asset_class_from_spec(spec_raw: Optional[Dict[str, Any]]) -> Optional[str]:
    if not spec_raw:
        return None
    text = " ".join(str(spec_raw.get(k) or "") for k in ("path", "category", "sector", "industry")).lower()
    if not text.strip():
        return None
    # "fx" alone would match inside words like "max"; require it as a path segment.
    segments = [seg for seg in text.replace("\\", " ").replace("/", " ").split() if seg]
    for needle, cls_name in _PATH_KEYWORDS:
        if needle == "fx":
            if "fx" in segments:
                return cls_name
            continue
        if needle in text:
            return cls_name
    return None


def asset_class(symbol: str, spec_raw: Optional[Dict[str, Any]], override: Optional[str]) -> "tuple[Optional[str], str]":
    """(class, source) with source in {env, spec.path, none}."""

    if override:
        return override, "env"
    cls_name = asset_class_from_spec(spec_raw)
    if cls_name:
        return cls_name, "spec.path"
    return None, "none"
