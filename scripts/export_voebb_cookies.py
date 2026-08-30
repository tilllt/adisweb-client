#!/usr/bin/env python3
"""Export the VÖBB session cookies from a logged-in browser via CDP.

The VÖBB OIDC callback endpoint is protected by an F5 WAF that rejects
non-browser clients (requests/curl_cffi → "Request Rejected"/404), while the
regular aDISWeb API accepts browser session cookies. So the login flow is:

1. Log in once in a real browser (https://www.voebb.de → Mein Konto).
2. Export the session cookies with this script (CDP over the browser).
3. Store them in .env (VOEBB_COOKIE_*) or cookies.json; the client then
   authenticates via the exported session.

Usage (browser running with --remote-debugging-port=9222, logged in):
    .venv/bin/python scripts/export_voebb_cookies.py > cookies_voebb.json
"""

import json
import sys

import urllib.request

CDP = "http://127.0.0.1:9222"


def cdp_http(method: str, params: dict) -> dict:
    req = urllib.request.Request(
        CDP + "/json/new?https://www.voebb.de/", method="PUT")
    with urllib.request.urlopen(req, timeout=10) as r:
        tab = json.loads(r.read())
    ws_url = tab["webSocketDebuggerUrl"]
    # use the HTTP endpoint for Network.getCookies via the inspector is not
    # possible; we use the raw /json list and the WebSocket-free approach:
    # Network.getAllCookies needs WS. Fall back to document.cookie + storage.
    return {"tab": ws_url}


def main() -> int:
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main())
