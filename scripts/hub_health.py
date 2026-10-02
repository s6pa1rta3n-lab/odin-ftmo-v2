#!/usr/bin/env python3
"""Print the hub's health snapshot as JSON.

Usage: python3 scripts/hub_health.py [/run/odin/metaapi-hub.sock]

Sends one ``health`` request over the unix socket and exits 0 on a reply.
Reads nothing else, sends no orders, never asks the hub to synchronize.
Exit 2 if the socket is missing or the hub does not answer within 10s.
"""

from __future__ import annotations

import json
import os
import socket
import sys

DEFAULT_SOCKET = os.environ.get("ODIN_METAAPI_HUB_SOCKET", "/run/odin/metaapi-hub.sock")


def main(argv: list[str]) -> int:
    path = argv[1] if len(argv) > 1 else DEFAULT_SOCKET
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(10.0)
    try:
        sock.connect(path)
        sock.sendall(b'{"id":"health-1","method":"health","params":{}}\n')
        buf = b""
        while not buf.endswith(b"\n"):
            chunk = sock.recv(65536)
            if not chunk:
                break
            buf += chunk
    except (OSError, socket.timeout) as exc:
        print(f"hub health failed at {path}: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    finally:
        sock.close()
    if not buf:
        print(f"hub health failed at {path}: empty reply", file=sys.stderr)
        return 2
    reply = json.loads(buf)
    print(json.dumps(reply.get("result", reply), indent=1, sort_keys=True))
    return 0 if reply.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
