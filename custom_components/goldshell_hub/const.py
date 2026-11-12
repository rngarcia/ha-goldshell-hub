"""Constants for the Goldshell Hub integration."""

from __future__ import annotations

from datetime import timedelta
from typing import Final

DOMAIN: Final = "goldshell_hub"

# Goldshell Hub cloud API (reverse-engineered from the hub.goldshell.com front end).
API_BASE: Final = "https://hub.goldshell.com/api/v1"

# Endpoints.
EP_CODE: Final = "/user/code"  # GET  -> QR login code + q_link
EP_CHECK: Final = "/user/check"  # GET  ?code=...  -> access_token once approved
EP_USERINFO: Final = "/user/userinfo"  # GET  (token header)
EP_MACHINES: Final = "/machines"  # GET  ?page=1&pagesize=100 (token header)

# Auth: the hub sends the JWT in a bare `token` header (not Authorization).
AUTH_HEADER: Final = "token"

# The hub issues ~30-day JWTs with no refresh endpoint. The QR login window is 5
# minutes; the front end polls /user/check every 5 seconds until approval.
QR_POLL_INTERVAL: Final = 5
QR_LOGIN_TIMEOUT: Final = 290  # a touch under the 5-minute code expiry

CONF_TOKEN: Final = "token"

DEFAULT_SCAN_INTERVAL: Final = timedelta(seconds=120)

# Machine status codes seen on the hub's /machines/filter/stats endpoint.
STATUS_MAP: Final = {
    100: "online",
    99: "offline",
    35: "idle",
    40: "fan_failure",
    50: "power_failure",
    60: "high_temp",
    29: "power_abnormal",
}
STATUS_ONLINE: Final = 100

MANUFACTURER: Final = "Goldshell"
