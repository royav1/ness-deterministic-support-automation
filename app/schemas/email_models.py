from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from app.schemas.chat_models import Intent


class EmailIngestRequest(BaseModel):
    message_id: str = Field(min_length=3, max_length=512, description="Email Message-ID (idempotency key)")
    from_email: str = Field(min_length=3, max_length=256)
    to_email: str = Field(min_length=3, max_length=256)
    subject: str = Field(default="", max_length=512)
    body: str = Field(default="", max_length=20000)

    # Optional override similar to chat
    company_id: Optional[str] = Field(default=None, description="Optional tenant/company identifier override")


class EmailIngestResponse(BaseModel):
    status: str = Field(description="processed | duplicate_skipped | pending_tenant")

    # Always echo back the idempotency key (very helpful for debugging + retries)
    message_id: str = Field(description="Echo of the idempotency key (Email Message-ID)")

    tenant_id: Optional[str] = None

    intent: Intent
    confidence: float

    internal_tags: List[str] = Field(default_factory=list)

    # preview only
    handoff_summary: Optional[Dict[str, Any]] = None
    jira_payload_preview: Optional[Dict[str, Any]] = None
