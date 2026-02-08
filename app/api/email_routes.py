import logging
from typing import Optional, Any, Dict

from fastapi import APIRouter, Header

from app.schemas.email_models import EmailIngestRequest, EmailIngestResponse
from app.storage.store_factory import get_memory, cleanup_if_supported
from app.email.email_router import process_email_to_jira_preview

router = APIRouter()
logger = logging.getLogger("chatbox")  # reuse same logger namespace


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

    # ---- Idempotency / dedupe (Option B: return stored receipt) ----
    if message_id and memory.is_email_processed(message_id):
        receipt: Optional[Dict[str, Any]] = None
        getter = getattr(memory, "get_email_receipt", None)
        if callable(getter):
            try:
                receipt = getter(message_id)
            except Exception:
                receipt = None

        logger.info(f"email_duplicate_skipped message_id={message_id}")

        if receipt and isinstance(receipt, dict):
            # Return the original receipt, but mark status as duplicate.
            # Also force the idempotency key to be present & correct.
            receipt_out = dict(receipt)
            receipt_out["status"] = "duplicate_skipped"
            receipt_out["message_id"] = message_id

            try:
                return EmailIngestResponse(**receipt_out)
            except Exception:
                # If schema changed and old receipts don't match, fallback cleanly.
                pass

        # Fallback if receipt not available / incompatible (should be rare)
        return EmailIngestResponse(
            status="duplicate_skipped",
            message_id=message_id or request.message_id,
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
        message_id=message_id or request.message_id,
        tenant_id=tenant_id,
        intent=intent,
        confidence=float(confidence),
        internal_tags=internal_tags,
        handoff_summary=handoff_summary,
        jira_payload_preview=jira_payload_preview,
    )

    # Mark processed + store receipt only if we truly processed (tenant known and payload built)
    if status == "processed" and message_id:
        memory.mark_email_processed(message_id)

        setter = getattr(memory, "set_email_receipt", None)
        if callable(setter):
            try:
                # Store "processed" receipt. On duplicates we override status to duplicate_skipped.
                setter(message_id, response.model_dump())
            except Exception:
                pass

    return response
