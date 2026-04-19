"""
SMS service for sending OTP via BulkSMS provider
"""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Dict
from urllib import request as urllib_request
from urllib.parse import urlencode

from app.core.config import settings


class SMSService:
    """
    Service for sending OTP SMS through BulkSMS API.
    """

    def __init__(self):
        self.api_key = settings.BULKSMS_API_KEY
        self.sender_id = settings.BULKSMS_SENDER_ID
        self.api_url = settings.BULKSMS_API_URL
        self.executor = ThreadPoolExecutor(max_workers=3)

    def _send_sms_sync(self, phone: str, message: str) -> bool:
        if not self.api_key or not self.sender_id or not self.api_url:
            print("SMS configuration missing: BULKSMS_API_KEY, BULKSMS_SENDER_ID, or BULKSMS_API_URL")
            return False

        payload: Dict[str, str] = {
            "api_key": self.api_key,
            "senderid": self.sender_id,
            "number": phone,
            "message": message,
            "type": "text",
        }

        try:
            # BulkSMSBD endpoint commonly expects query params over GET.
            encoded_payload = urlencode(payload)
            endpoint = f"{self.api_url}?{encoded_payload}"
            req = urllib_request.Request(endpoint, method="GET")

            with urllib_request.urlopen(req, timeout=15) as response:
                raw = response.read().decode("utf-8", errors="ignore")

            normalized = raw.strip().lower()

            # Many gateways return JSON: {"response_code":200/202, ...}
            try:
                response_json = json.loads(raw)
                response_code = str(response_json.get("response_code", "")).strip()
                if response_code in {"200", "202"}:
                    return True
                if response_code:
                    print(f"SMS API returned error code {response_code}: {raw}")
                    return False
            except Exception:
                pass

            # Provider may return plain-text status messages.
            success_tokens = {"success", "accepted", "sent", "queued", "sms submitted"}
            if any(token in normalized for token in success_tokens):
                return True

            # Provider may also return numeric status codes where non-200 indicates failure.
            if normalized.isdigit() and normalized != "200":
                print(f"SMS API returned error code {normalized}: {raw}")
                return False

            if any(flag in normalized for flag in ["error", "failed", "invalid", "unauthorized", "insufficient"]):
                print(f"SMS API returned failure response: {raw}")
                return False

            # Unknown responses are treated as failure to avoid false-positive delivery status.
            print(f"SMS API returned unknown response: {raw}")
            return False
        except Exception as exc:
            print(f"Failed to send SMS OTP to {phone}: {exc}")
            return False

    async def send_otp_sms(self, phone: str, otp_code: str) -> bool:
        message = f"Your CricGeo login code is {otp_code}. Please do not share this code with anyone. It is valid for 5 minutes."
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, self._send_sms_sync, phone, message)


sms_service = SMSService()
