"""
HMAC-SHA256 webhook signing and Power Automate submission.
In mock mode (when PA URLs are blank) — logs the payload and returns simulated success.
"""
import hmac
import hashlib
import json
import logging
from datetime import datetime

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def _sign(payload: dict) -> str:
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True)
    sig = hmac.new(
        settings.WEBHOOK_SECRET.encode(),
        body.encode(),
        hashlib.sha256,
    ).hexdigest()
    return sig


async def send(payload: dict, passed: bool) -> dict:
    """
    Send signed payload to Power Automate proceed or reject URL.
    Returns {"status": "sent"|"mocked", "response_code": int, "url": str}.
    """
    url = settings.POWER_AUTOMATE_PROCEED_URL if passed else settings.POWER_AUTOMATE_REJECT_URL

    if settings.pa_mock_mode:
        logger.info(
            f"[webhook] MOCK MODE — would POST to {'PROCEED' if passed else 'REJECT'} URL. "
            f"Payload: {json.dumps(payload, indent=2)[:300]}..."
        )
        return {
            "status": "mocked",
            "response_code": 200,
            "url": "(mock — no PA URL configured)",
            "mock": True,
        }

    signature = _sign(payload)
    headers = {
        "Content-Type": "application/json",
        "X-DAFF-Signature": signature,
        "X-DAFF-Timestamp": datetime.utcnow().isoformat(),
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json=payload, headers=headers)

    logger.info(f"[webhook] POST {url} → {resp.status_code}")
    return {
        "status": "sent",
        "response_code": resp.status_code,
        "url": url,
        "mock": False,
    }
