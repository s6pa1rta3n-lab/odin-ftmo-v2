"""Asset-class classification from the broker's symbol group (MT5 ``path``) and name.

The class only selects the default commission model; it is never used to guess a
spec value. Priority:

1. ``AUTOEXEC_ASSET_CLASS_<SYMBOL>`` override.
2. Symbol-name exceptions inside shared groups (FTMO symbols page, 2026-10-08):
   ``USOIL.cash`` / ``UKOIL.cash`` -> ``oil``; ``NATGAS.cash`` / ``HEATOIL.c`` ->
   ``energy``; ``DXY.cash`` -> ``dollar_index``; other ``*.c`` -> ``agri``.
3. The first path segment (broker group), case-insensitively: ``Crypto``,
   ``Crypto CFD``, ``Crypto II CFD`` -> ``crypto``; ``Forex``/``Exotics`` -> ``forex``;
   ``Metals CFD`` -> ``metals``; ``Cash CFD``/``Indices`` -> ``index``;
   ``Equities CFD``/``Stocks`` -> ``equity``; ``Agricultural`` -> ``agri``.
4. Unknown -> None (no default commission; explicit env needed).

Slash names (``XAU/USD``) are normalised to ``XAUUSD`` before matching.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

ASSET_CLASSES = ("crypto", "forex", "metals", "index", "oil", "equity", "energy", "dollar_index", "agri")

# symbol-name exceptions (upper-cased, slashes removed)
_NAME_MAP = {
    "USOIL.CASH": "oil",
    "UKOIL.CASH": "oil",
    "NATGAS.CASH": "energy",
    "HEATOIL.C": "energy",
    "DXY.CASH": "dollar_index",
}

# (needle in the lower-cased group / path, class) — order matters
_GROUP_KEYWORDS = (
    ("crypto", "crypto"),
    ("forex", "forex"),
    ("exotic", "forex"),
    ("currenc", "forex"),
    ("metal", "metals"),
    ("gold", "metals"),
    ("silver", "metals"),
    ("equit", "equity"),
    ("stock", "equity"),
    ("share", "equity"),
    ("agri", "agri"),
    ("cash cfd", "index"),
    ("indic", "index"),
    ("index", "index"),
)


def normalize_symbol(symbol: Optional[str]) -> str:
    """``xau/usd`` -> ``XAUUSD`` for matching against page codes / name maps."""

    return str(symbol or "").replace("/", "").strip().upper()


def _group_text(spec_raw: Dict[str, Any]) -> str:
    path = str(spec_raw.get("path") or "")
    group = path.replace("/", "\\").split("\\")[0] if path else ""
    extra = " ".join(str(spec_raw.get(k) or "") for k in ("category", "sector", "industry"))
    return f"{group} {extra} {path}".lower()


def asset_class_from_name(symbol: Optional[str]) -> Optional[str]:
    name = normalize_symbol(symbol)
    if not name:
        return None
    if name in _NAME_MAP:
        return _NAME_MAP[name]
    if name.endswith(".C"):
        return "agri"
    return None


def asset_class_from_spec(spec_raw: Optional[Dict[str, Any]]) -> Optional[str]:
    if not spec_raw:
        return None
    text = _group_text(spec_raw)
    if not text.strip():
        return None
    segments = [seg for seg in text.replace("\\", " ").replace("/", " ").split() if seg]
    if "fx" in segments:
        return "forex"
    for needle, cls_name in _GROUP_KEYWORDS:
        if needle in text:
            return cls_name
    return None


def asset_class(symbol: str, spec_raw: Optional[Dict[str, Any]], override: Optional[str]) -> "tuple[Optional[str], str]":
    """(class, source) with source in {env, name, spec.path, none}."""

    if override:
        return override, "env"
    by_name = asset_class_from_name(symbol or (spec_raw or {}).get("symbol"))
    if by_name:
        return by_name, "name"
    cls_name = asset_class_from_spec(spec_raw)
    if cls_name:
        return cls_name, "spec.path"
    return None, "none"
