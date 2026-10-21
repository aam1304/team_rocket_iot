"""
alerts.py
---------
Posts a message to the team's Discord channel via webhook, for
failures that shouldn't happen silently: the real sensor module
failing to import, the main loop repeatedly erroring, or the DHT22
failing many times in a row.
 """

import json
import urllib.request
from config import DISCORD_WEBHOOK_URL


def send_alert(message: str) -> None:
    """Posts `message` to the configured Discord webhook."""
    if not DISCORD_WEBHOOK_URL:
        print(f"[ALERT] (no webhook configured) {message}")
        return

    try:
        payload = json.dumps({
            "content": f"**Team Rocket rig:** {message}"
        }).encode("utf-8")

        req = urllib.request.Request(
            DISCORD_WEBHOOK_URL,
            data=payload,
            headers={
                "Content-Type": "application/json",
                "User-Agent": "TeamRocket-IoT/1.0",
            },
        )

        urllib.request.urlopen(req, timeout=5)

    except Exception as e:
        print(f"[WARN] Discord alert failed to send: {e}")