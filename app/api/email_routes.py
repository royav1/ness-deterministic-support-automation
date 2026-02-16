import logging
from typing import Optional, List

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.schemas.email_models import EmailIngestRequest, EmailIngestResponse
from app.storage.store_factory import get_memory, cleanup_if_supported
from app.email.email_service import (
    ingest_email_service,
    resolve_email_service,
    list_pending_emails_service,
)

router = APIRouter()
logger = logging.getLogger("chatbox")


# ---------------------------------------------------------------------
# MODELS
# ---------------------------------------------------------------------

class EmailResolveRequest(BaseModel):
    message_id: str = Field(min_length=3, max_length=512)
    company_id: Optional[str] = Field(default=None)


class EmailPendingListResponse(BaseModel):
    pending: List[str] = Field(default_factory=list)


# ---------------------------------------------------------------------
# EMAIL INGEST
# ---------------------------------------------------------------------

@router.post("/email/ingest", response_model=EmailIngestResponse)
def ingest_email(
    request: EmailIngestRequest,
    x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
) -> EmailIngestResponse:

    memory = get_memory()
    expired = cleanup_if_supported(memory)
    if expired:
        logger.info(f"cleanup_expired removed={expired}")

    if not request.message_id:
        raise HTTPException(status_code=422, detail="message_id is required")

    return ingest_email_service(
        memory=memory,
        request=request,
        x_company_id=x_company_id,
        logger=logger,
    )


# ---------------------------------------------------------------------
# EMAIL RESOLVE
# ---------------------------------------------------------------------

@router.post("/email/resolve", response_model=EmailIngestResponse)
def resolve_email(
    request: EmailResolveRequest,
    x_company_id: Optional[str] = Header(default=None, alias="X-Company-Id"),
) -> EmailIngestResponse:

    memory = get_memory()
    expired = cleanup_if_supported(memory)
    if expired:
        logger.info(f"cleanup_expired removed={expired}")

    message_id = (request.message_id or "").strip()
    if not message_id:
        raise HTTPException(status_code=422, detail="message_id is required")

    company_id = (x_company_id or request.company_id or "").strip()
    if not company_id:
        raise HTTPException(
            status_code=422,
            detail="company_id is required (X-Company-Id header or body)",
        )

    return resolve_email_service(
        memory=memory,
        message_id=message_id,
        company_id=company_id,
        logger=logger,
    )


# ---------------------------------------------------------------------
# LIST PENDING
# ---------------------------------------------------------------------

@router.get("/email/pending", response_model=EmailPendingListResponse)
def list_pending_emails() -> EmailPendingListResponse:
    memory = get_memory()
    pending_ids = list_pending_emails_service(memory)
    return EmailPendingListResponse(pending=pending_ids)
