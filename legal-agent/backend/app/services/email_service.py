"""SMTP email helper for performance alerts."""
from __future__ import annotations

import logging
import smtplib
import ssl
from email.message import EmailMessage

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def send_mail(to: str, subject: str, body: str) -> tuple[bool, str]:
    """Send plain-text email. Returns (ok, error_or_skip_reason)."""
    settings = get_settings()
    to = (to or "").strip()
    if not to:
        return False, "收件人邮箱为空"
    if not settings.smtp_enabled:
        logger.info("SMTP disabled, skip mail to=%s subject=%s", to, subject)
        return False, "smtp_disabled"
    if not settings.smtp_host:
        return False, "smtp_host 未配置"

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = settings.smtp_from or settings.smtp_user or "noreply@legal-agent.local"
    msg["To"] = to
    msg.set_content(body)

    try:
        if settings.smtp_use_ssl:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, context=context, timeout=20) as server:
                if settings.smtp_user:
                    server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as server:
                if settings.smtp_use_tls:
                    server.starttls(context=ssl.create_default_context())
                if settings.smtp_user:
                    server.login(settings.smtp_user, settings.smtp_password)
                server.send_message(msg)
        return True, ""
    except Exception as exc:  # noqa: BLE001
        logger.exception("send_mail failed to=%s", to)
        return False, str(exc)
