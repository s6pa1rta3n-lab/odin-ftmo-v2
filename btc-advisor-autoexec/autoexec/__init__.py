"""BTC Advisor auto-execution endpoint for FTMO (MetaAPI REST, London host).

Order placement is DISABLED by default (``AUTOEXEC_ORDERS_ENABLED=0``). Every
guard runs against live read-only data in dry-run; nothing is sent.

Authorization: Odin James, Strategy Implementer chat, 2026-10-10 05:45 ET;
equity-halt and commission-fallback correction 2026-10-10 05:47 ET.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
