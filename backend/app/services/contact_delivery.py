from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from functools import lru_cache
from typing import Protocol

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ContactMessage:
    name: str
    email: str
    company: str | None
    subject: str
    message: str


class ContactDeliveryError(RuntimeError):
    """Raised when a validated contact message cannot be delivered."""


class ContactDelivery(Protocol):
    def deliver(self, message: ContactMessage) -> None: ...


class SinkContactDelivery:
    """Local transport that proves delivery flow without retaining message content."""

    def deliver(self, message: ContactMessage) -> None:
        logger.info(
            "Contact sink accepted message "
            "(subject_chars=%d, message_chars=%d, company=%s)",
            len(message.subject),
            len(message.message),
            bool(message.company),
        )


class DisabledContactDelivery:
    def deliver(self, message: ContactMessage) -> None:
        del message
        raise ContactDeliveryError("Contact delivery is not configured")


class SmtpContactDelivery:
    def __init__(self, settings: Settings) -> None:
        if (
            not settings.smtp_host
            or not settings.smtp_from
            or not settings.contact_recipient_email
        ):
            raise ContactDeliveryError("SMTP contact delivery is incomplete")
        self.settings = settings

    def deliver(self, message: ContactMessage) -> None:
        host = self.settings.smtp_host
        if host is None:
            raise ContactDeliveryError("SMTP contact delivery is incomplete")
        email = EmailMessage()
        email["Subject"] = f"Husky Tracking contact: {message.subject}"
        email["From"] = self.settings.smtp_from
        email["To"] = self.settings.contact_recipient_email
        email["Reply-To"] = message.email
        company = message.company or "Not provided"
        email.set_content(
            "New Husky Tracking project message\n\n"
            f"Name: {message.name}\n"
            f"Email: {message.email}\n"
            f"Company / organization: {company}\n\n"
            f"Message:\n{message.message}"
        )
        try:
            with smtplib.SMTP(
                host,
                self.settings.smtp_port,
                timeout=self.settings.smtp_timeout_seconds,
            ) as client:
                if self.settings.smtp_starttls:
                    client.starttls()
                if self.settings.smtp_username:
                    client.login(
                        self.settings.smtp_username,
                        self.settings.smtp_password or "",
                    )
                client.send_message(email)
        except (OSError, smtplib.SMTPException) as error:
            raise ContactDeliveryError("Contact delivery failed") from error


@lru_cache
def get_contact_delivery() -> ContactDelivery:
    settings = get_settings()
    if settings.contact_delivery_mode == "sink":
        return SinkContactDelivery()
    if settings.contact_delivery_mode == "disabled":
        return DisabledContactDelivery()
    try:
        return SmtpContactDelivery(settings)
    except ContactDeliveryError:
        logger.error("SMTP contact delivery configuration is incomplete")
        return DisabledContactDelivery()
