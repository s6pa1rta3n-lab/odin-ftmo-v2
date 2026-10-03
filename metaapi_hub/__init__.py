"""Shared MetaAPI hub for Odin's FTMO engines.

The hub is infrastructure only. It does not change strategy logic.

Default is off. Engines keep opening their own MetaApiWrapper until
``ODIN_METAAPI_HUB`` is set to ``on`` or ``shadow``. This package does not
enable live trading and does not install or edit systemd units.
"""

from __future__ import annotations

__version__ = "1.0.0"

# Live cutover is intentionally not the default. See docs/metaapi_hub/CUTOVER.md.
DEFAULT_HUB_MODE = "off"
"""Shipped default. Do not change this to on or shadow."""
