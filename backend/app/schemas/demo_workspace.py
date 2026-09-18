from datetime import datetime

from pydantic import BaseModel


class DemoSessionRead(BaseModel):
    active: bool = True
    expires_at: datetime
    ttl_hours: int
    ttl_seconds: int
    created: bool
    replaced_expired: bool


class DemoResetRead(BaseModel):
    status: str
    expires_at: datetime


class PrivacyRead(BaseModel):
    controller_name: str
    contact_email: str
    controller_country: str
    hosting_region: str
    effective_date: str
    mail_provider_name: str | None
    mail_provider_region: str | None
    demo_workspace_ttl_hours: int
