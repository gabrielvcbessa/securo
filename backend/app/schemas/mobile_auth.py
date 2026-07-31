import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class MobileLoginRequest(BaseModel):
    email: str
    password: str
    device_name: str = Field(min_length=1, max_length=100)
    totp_code: str | None = Field(default=None, pattern=r"^\d{6}$")


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=32)


class MobileTokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int
    session_id: uuid.UUID


class MobileSessionRead(BaseModel):
    id: uuid.UUID
    device_name: str
    created_at: datetime
    last_used_at: datetime
    expires_at: datetime
    revoked_at: datetime | None
