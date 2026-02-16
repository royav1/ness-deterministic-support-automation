from __future__ import annotations

from typing import Any, Dict, Optional, List, Tuple

from app.schemas.email_models import EmailIngestRequest, EmailIngestResponse
from app.email.email_router import (
    process_email_to_jira_preview,
    process_email_resolution_to_jira_preview,
)


# ---------------------------------------------------------------------
# Small safe helpers (moved from router)
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
# INGEST SERVICE
# ---------------------------------------------------------------------

def ingest_email_service(
    *,
    memory: Any,
    request: EmailIngestRequest,
    x_company_id: Optional[str],
    logger: Any,
) -> EmailIngestResponse:

    message_id = (request.message_id or "").strip()

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

    # ---- Pending tenant ----
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

    # ---- Processed ----
    if status == "processed":
        memory.mark_email_processed(message_id)
        _try_set_receipt(memory, message_id, response.model_dump())
        _try_clear_pending(memory, message_id)

    return response


# ---------------------------------------------------------------------
# RESOLVE SERVICE (Mode B)
# ---------------------------------------------------------------------

def resolve_email_service(
    *,
    memory: Any,
    message_id: str,
    company_id: str,
    logger: Any,
) -> EmailIngestResponse:

    message_id = (message_id or "").strip()

    # ---- Already processed ----
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

    if status == "pending_tenant":
        logger.info(
            f"email_resolve_still_pending message_id={message_id} company_id={company_id}"
        )
        return response

    if status == "processed":
        memory.mark_email_processed(message_id)
        _try_set_receipt(memory, message_id, response.model_dump())
        _try_clear_pending(memory, message_id)
        logger.info(
            f"email_resolved_processed message_id={message_id} tenant_id={tenant_id}"
        )

    return response


# ---------------------------------------------------------------------
# LIST PENDING SERVICE
# ---------------------------------------------------------------------

def list_pending_emails_service(memory: Any) -> List[str]:
    return _try_list_pending(memory)
