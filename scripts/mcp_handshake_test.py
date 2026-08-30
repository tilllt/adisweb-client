#!/usr/bin/env python3
"""MCP stdio handshake test: initialize -> tools/list against adisweb.mcp_server."""

import json
import subprocess
import sys
import time

PROC = [sys.executable, "-m", "adisweb.mcp_server"]


def send(proc, msg: dict) -> None:
    proc.stdin.write(json.dumps(msg) + "\n")
    proc.stdin.flush()


def read_until(proc, marker: str, timeout: float = 30.0) -> dict:
    deadline = time.time() + timeout
    buf = ""
    while time.time() < deadline:
        line = proc.stdout.readline()
        if not line:
            break
        buf += line
        if marker in line:
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    raise TimeoutError(f"marker '{marker}' not seen; buffered: {buf[-300:]!r}")


def main() -> int:
    proc = subprocess.Popen(
        PROC, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, cwd=sys.path[0] or ".",
        bufsize=1,
    )
    try:
        send(proc, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                    "params": {"protocolVersion": "2025-06-18",
                               "capabilities": {}, "clientInfo": {"name": "handshake-test", "version": "0"}}})
        init = read_until(proc, '"result"')
        print("initialize OK | server:", init["result"]["serverInfo"]["name"],
              init["result"]["serverInfo"]["version"])

        send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})
        send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        tl = read_until(proc, '"tools"')
        names = [t["name"] for t in tl["result"]["tools"]]
        print("tools/list:", names)

        # call list_libraries via stdio
        send(proc, {"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                    "params": {"name": "list_libraries", "arguments": {}}})
        call = read_until(proc, '"content"')
        texts = [c.get("text", "") for c in call["result"]["content"]]
        print("tools/call list_libraries ->", len(json.loads(texts[0])), "libs")

        # search (live)
        send(proc, {"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                    "params": {"name": "search", "arguments": {"query": "Berlin"}}})
        call = read_until(proc, '"content"')
        texts = [c.get("text", "") for c in call["result"]["content"]]
        data = json.loads(texts[0])
        print("tools/call search -> total:", data["total"], "| hits:", len(data["results"]))
        print("HANDSHAKE + TOOLS OK")
        return 0
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    sys.exit(main())
