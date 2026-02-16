import logging
from typing import Optional, Any, Dict, List

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.schemas.email_models import EmailIngestRequest, EmailIngestResponse
from app.storage.store_factory import get_memory, cleanup_if_supported
from app.email.email_router import (
    process_email_to_jira_preview,
    process_email_resolution_to_jira_preview,
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
# Small safe helpers
# ---------------------------------------------------------------------

def _try_get_receipt(memory: Any, message_id: str) -> Optional[Dict[str, Any]]:
    getter = getattr(memory, "get_email_receipt", None)
    if callable(getter):
        try:
            receipt = getter(message_id)
            return receipt if isinstance(receipt, dict) else None
        except Exception:
            return None
    return None


def _try_set_receipt(memory: Any, message_id: str, receipt: Dict[str, Any]) -> None:
    setter = getattr(memory, "set_email_receipt", None)
    if callable(setter):
        try:
            setter(message_id, receipt)
        except Exception:
            pass


def _try_set_pending(memory: Any, message_id: str, payload: Dict[str, Any]) -> None:
    setter = getattr(memory, "set_pending_email", None)
    if callable(setter):
        try:
            setter(message_id, payload)
        except Exception:
            pass


def _try_clear_pending(memory: Any, message_id: str) -> None:
    clearer = getattr(memory, "clear_pending_email", None)
    if callable(clearer):
        try:
            clearer(message_id)
        except Exception:
            pass


def _try_list_pending(memory: Any) -> List[str]:
    lister = getattr(memory, "list_pending_emails", None)
    if callable(lister):
        try:
            result = lister()
            return result if isinstance(result, list) else []
        except Exception:
            return []
    return []


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

    message_id = (request.message_id or "").strip()
    if not message_id:
        raise HTTPException(status_code=422, detail="message_id is required")

    # ---- Idempotency ----
    if memory.is_email_processed(message_id):
        receipt = _try_get_receipt(memory, message_id)
        logger.info(f"email_duplicate_skipped message_id={message_id}")

        if receipt:
            receipt_out = dict(receipt)
            receipt_out["status"] = "duplicate_skipped"
            receipt_out["message_id"] = message_id
            try:
                return EmailIngestResponse(**receipt_out)
            except Exception:
                pass

        return EmailIngestResponse(
            status="duplicate_skipped",
            message_id=message_id,
            tenant_id=None,
            intent="UNKNOWN",
            confidence=0.0,
            internal_tags=[],
            handoff_summary=None,
            jira_payload_preview=None,
        )

    # ---- Normal processing ----
    (
        status,
        tenant_id,
        intent,
        confidence,
        internal_tags,
        handoff_summary,
        jira_payload_preview,
    ) = process_email_to_jira_preview(
        memory=memory,
        req=request,
        x_company_id=x_company_id,
        logger=logger,
    )

    response = EmailIngestResponse(
        status=status,
        message_id=message_id,
        tenant_id=tenant_id,
        intent=intent,
        confidence=float(confidence),
        internal_tags=internal_tags,
        handoff_summary=handoff_summary,
        jira_payload_preview=jira_payload_preview,
    )

    # ---- Pending tenant → store for Mode B ----
    if status == "pending_tenant":
        _try_set_pending(
            memory,
            message_id,
            {
                "handoff_summary": handoff_summary,
                "intent": intent,
                "confidence": confidence,
                "internal_tags": internal_tags,
            },
        )
        logger.info(f"email_pending_saved message_id={message_id}")
        return response

    # ---- Processed → finalize ----
    if status == "processed":
        memory.mark_email_processed(message_id)
        _try_set_receipt(memory, message_id, response.model_dump())
        _try_clear_pending(memory, message_id)

    return response


# ---------------------------------------------------------------------
# EMAIL RESOLVE (Mode B)
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

    # ---- Already processed? behave like idempotency ----
    if memory.is_email_processed(message_id):
        receipt = _try_get_receipt(memory, message_id)
        logger.info(f"email_resolve_duplicate message_id={message_id}")

        if receipt:
            receipt_out = dict(receipt)
            receipt_out["status"] = "duplicate_skipped"
            receipt_out["message_id"] = message_id
            try:
                return EmailIngestResponse(**receipt_out)
            except Exception:
                pass

        return EmailIngestResponse(
            status="duplicate_skipped",
            message_id=message_id,
            tenant_id=None,
            intent="UNKNOWN",
            confidence=0.0,
            internal_tags=[],
            handoff_summary=None,
            jira_payload_preview=None,
        )

    # ---- Resolve tenant ----
    company_id = (x_company_id or request.company_id or "").strip()
    if not company_id:
        raise HTTPException(
            status_code=422,
            detail="company_id is required (X-Company-Id header or body)",
        )

    (
        status,
        tenant_id,
        intent,
        confidence,
        internal_tags,
        handoff_summary,
        jira_payload_preview,
    ) = process_email_resolution_to_jira_preview(
        memory=memory,
        message_id=message_id,
        company_id=company_id,
        logger=logger,
    )

    response = EmailIngestResponse(
        status=status,
        message_id=message_id,
        tenant_id=tenant_id,
        intent=intent,
        confidence=float(confidence),
        internal_tags=internal_tags,
        handoff_summary=handoff_summary,
        jira_payload_preview=jira_payload_preview,
    )

    # ---- Still pending (wrong tenant?) ----
    if status == "pending_tenant":
        logger.info(
            f"email_resolve_still_pending message_id={message_id} company_id={company_id}"
        )
        return response

    # ---- Successfully processed ----
    if status == "processed":
        memory.mark_email_processed(message_id)
        _try_set_receipt(memory, message_id, response.model_dump())
        _try_clear_pending(memory, message_id)
        logger.info(
            f"email_resolved_processed message_id={message_id} tenant_id={tenant_id}"
        )

    return response


# ---------------------------------------------------------------------
# LIST PENDING EMAILS (Admin / Debug Utility)
# ---------------------------------------------------------------------

@router.get("/email/pending", response_model=EmailPendingListResponse)
def list_pending_emails() -> EmailPendingListResponse:
    """
    Returns list of message_ids currently waiting for tenant resolution.
    Works for both MemoryStore and RedisMemoryStore.
    """
    memory = get_memory()
    pending_ids = _try_list_pending(memory)
    return EmailPendingListResponse(pending=pending_ids)
