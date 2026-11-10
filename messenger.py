"""Instagram'ga xabar yuborish va menejerga Telegram orqali xabarnoma."""
import hashlib
import hmac
import logging
import os

import httpx

log = logging.getLogger("messenger")

IG_TOKEN = os.getenv("IG_ACCESS_TOKEN", "")
IG_API = os.getenv("IG_API_URL", "https://graph.instagram.com/v21.0/me/messages")
APP_SECRET = os.getenv("META_APP_SECRET", "")
TG_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TG_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")


def verify_signature(body: bytes, header: str | None) -> bool:
    """Meta webhook imzosini tekshiradi (X-Hub-Signature-256)."""
    if not APP_SECRET:
        log.warning("META_APP_SECRET berilmagan — imzo tekshirilmayapti")
        return True
    if not header or not header.startswith("sha256="):
        return False
    expected = hmac.new(APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, header[7:])


def send_instagram(recipient_id: str, text: str) -> bool:
    if not IG_TOKEN:
        log.info("[IG test rejimi] %s <- %s", recipient_id, text)
        return True
    try:
        r = httpx.post(
            IG_API,
            headers={"Authorization": f"Bearer {IG_TOKEN}"},
            json={"recipient": {"id": recipient_id}, "message": {"text": text[:1000]}},
            timeout=15,
        )
        if r.status_code >= 400:
            log.error("Instagram xatosi %s: %s", r.status_code, r.text)
            return False
        return True
    except httpx.HTTPError as e:
        log.error("Instagram'ga ulanib bo'lmadi: %s", e)
        return False


def notify_manager(text: str) -> None:
    """Yangi ariza haqida menejerning Telegram'iga qisqa xabar (ixtiyoriy)."""
    if not (TG_TOKEN and TG_CHAT):
        return
    try:
        httpx.post(
            f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage",
            json={"chat_id": TG_CHAT, "text": text},
            timeout=10,
        )
    except httpx.HTTPError as e:
        log.error("Telegram xabarnoma yuborilmadi: %s", e)
