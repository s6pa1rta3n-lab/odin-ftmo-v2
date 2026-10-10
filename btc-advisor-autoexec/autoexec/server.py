"""Small local HTTP endpoint (stdlib ``http.server``), loopback by default.

Routes (JSON in, JSON out):

* ``GET  /health``            — liveness; never touches the broker.
* ``GET  /status``            — read-only guard states from live data.
* ``POST /setup``             — entry decision. Body: ``{"side","entry_type","stop","target"}``
                                plus optional ``request_id``, ``dry_run``.
* ``POST /tighten``           — tighten the auto position's stop. Body: ``{"stop"}``
                                plus optional ``position_id``, ``request_id``, ``dry_run``.

If ``AUTOEXEC_API_KEY`` is set every request must carry ``X-Autoexec-Key``.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional, Tuple

from .engine import Executor
from .jsonlog import redact


class _Handler(BaseHTTPRequestHandler):
    executor: Executor  # set on the server class by make_server
    api_key: str = ""
    server_version = "btc-advisor-autoexec"
    sys_version = ""

    # ---- helpers

    def _send(self, status: int, body: Dict[str, Any]) -> None:
        payload = json.dumps(body, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def _authorized(self) -> bool:
        if not self.api_key:
            return True
        return self.headers.get("X-Autoexec-Key", "") == self.api_key

    def _read_json(self) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
        length = int(self.headers.get("Content-Length") or 0)
        if length > 64 * 1024:
            return None, "body too large"
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}, None
        try:
            data = json.loads(raw.decode("utf-8"))
        except ValueError as exc:
            return None, f"invalid JSON: {exc}"
        if not isinstance(data, dict):
            return None, "body must be a JSON object"
        return data, None

    def log_message(self, fmt: str, *args: Any) -> None:  # route access logs to the JSON logger
        self.executor.log.emit("http", client=self.client_address[0], line=fmt % args)

    # ---- routes

    def do_GET(self) -> None:  # noqa: N802
        if not self._authorized():
            self._send(401, {"ok": False, "code": "UNAUTHORIZED", "reason": "missing or wrong X-Autoexec-Key"})
            return
        if self.path == "/health":
            self._send(200, {"ok": True, "armed": self.executor.armed, "orders_enabled": self.executor.cfg.orders_enabled, "kill_active": self.executor.cfg.kill_active})
            return
        if self.path == "/status":
            st = self.executor.status()
            st.pop("reads", None)
            self._send(200 if st.get("ok") else 503, redact(st))
            return
        self._send(404, {"ok": False, "code": "NOT_FOUND"})

    def do_POST(self) -> None:  # noqa: N802
        if not self._authorized():
            self._send(401, {"ok": False, "code": "UNAUTHORIZED", "reason": "missing or wrong X-Autoexec-Key"})
            return
        body, err = self._read_json()
        if err or body is None:
            self._send(400, {"ok": False, "code": "BAD_REQUEST", "reason": err or "no body"})
            return
        force_dry = bool(body.pop("dry_run", False))
        if self.path == "/setup":
            decision = self.executor.decide_entry(body, force_dry_run=force_dry)
        elif self.path == "/tighten":
            decision = self.executor.tighten_stop(body, force_dry_run=force_dry)
        else:
            self._send(404, {"ok": False, "code": "NOT_FOUND"})
            return
        decision = dict(decision)
        decision["ok"] = bool(decision.get("accepted"))
        self._send(200, redact(decision))


def make_server(executor: Executor, *, host: str, port: int, api_key: str = "") -> ThreadingHTTPServer:
    handler = type("AutoexecHandler", (_Handler,), {"executor": executor, "api_key": api_key})
    server = ThreadingHTTPServer((host, port), handler)
    server.daemon_threads = True
    return server


def serve_forever(executor: Executor) -> None:
    cfg = executor.cfg
    server = make_server(executor, host=cfg.bind_host, port=cfg.bind_port, api_key=cfg.api_key)
    executor.log.emit(
        "server_start",
        bind=f"{cfg.bind_host}:{cfg.bind_port}",
        orders_enabled=cfg.orders_enabled,
        kill_active=cfg.kill_active,
        armed=executor.armed,
        halt_latched=executor.halt.active,
        config=cfg.public_dict(),
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        executor.log.emit("server_stop")
