from __future__ import annotations

from typing import Any, Dict, Optional, Tuple, List

from app.schemas.chat_models import Intent
from app.schemas.email_models import EmailIngestRequest
from app.services.classifier import classify
from app.tenants.tenant_gate import validate_and_get_tenant
from app.jira.handoff_service import (
    ensure_internal_tags,
    get_internal_tags,
    build_vpn_payload_preview,
    build_generic_payload_preview,
)

from app.email.tenant_inference import infer_tenant_id_from_to_email
from app.email.summary_builder import build_handoff_summary_from_email
from app.email.pending_store import (
    store_pending_email,
    get_pending_email,
    clear_pending_email,
)


# ---------------------------------------------------------------------
# Main processor (INGEST)
# ---------------------------------------------------------------------

def process_email_to_jira_preview(
    *,
    memory: Any,
    req: EmailIngestRequest,
    x_company_id: Optional[str],
    logger: Any,
) -> Tuple[str, Optional[str], Intent, float, List[str], Dict[str, Any], Optional[Dict[str, Any]]]:

    # ---- Tenant resolution ----
    inferred_tenant = infer_tenant_id_from_to_email(req.to_email)

    candidate_company_id = (
        x_company_id
        or req.company_id
        or inferred_tenant
        or ""
    ).strip()

    tenant, valid = (
        validate_and_get_tenant(candidate_company_id)
        if candidate_company_id
        else (None, False)
    )

    # ---- Intent classification ----
    text = f"{req.subject}\n{req.body}".strip()
    intent, confidence = classify(text, previous_intent=None)

    # ---- Build handoff summary ----
    handoff_summary = build_handoff_summary_from_email(req, intent)

    ensure_internal_tags(handoff_summary)
    internal_tags = get_internal_tags(handoff_summary)

    # ---- Missing tenant → pending ----
    if tenant is None:

        pending_payload: Dict[str, Any] = {
            "message_id": req.message_id,
            "intent": intent,
            "confidence": float(confidence),
            "internal_tags": internal_tags,
            "handoff_summary": handoff_summary,
            "candidate_company_id": candidate_company_id or None,
            "inferred_from_email": inferred_tenant,
        }

        store_pending_email(
            memory=memory,
            message_id=req.message_id,
            payload=pending_payload,
        )

        logger.info(
            f"email_pending_tenant message_id={req.message_id} "
            f"candidate_company_id={candidate_company_id or None} "
            f"inferred_from_email={inferred_tenant} "
            f"intent={intent} conf={confidence:.2f}"
        )

        return (
            "pending_tenant",
            None,
            intent,
            confidence,
            internal_tags,
            handoff_summary,
            None,
        )

    # ---- Build Jira payload preview ----
    if intent == "VPN_ISSUE":
        jira_payload_preview, labels = build_vpn_payload_preview(
            session_id=req.message_id,
            tenant=tenant,
            handoff_summary=handoff_summary,
        )
    else:
        jira_payload_preview, labels = build_generic_payload_preview(
            correlation_id=req.message_id,
            tenant=tenant,
            handoff_summary=handoff_summary,
        )

    logger.info(
        f"email_processed message_id={req.message_id} "
        f"tenant_id={tenant.tenant_id} "
        f"intent={intent} conf={confidence:.2f} labels={labels}"
    )

    return (
        "processed",
        tenant.tenant_id,
        intent,
        confidence,
        internal_tags,
        handoff_summary,
        jira_payload_preview,
    )


# ---------------------------------------------------------------------
# Mode B: resolve pending email
# ---------------------------------------------------------------------

def process_email_resolution_to_jira_preview(
    *,
    memory: Any,
    message_id: str,
    company_id: str,
    logger: Any,
) -> Tuple[str, Optional[str], Intent, float, List[str], Dict[str, Any], Optional[Dict[str, Any]]]:

    mid = (message_id or "").strip()
    cid = (company_id or "").strip()

    if not mid or not cid:
        logger.info(
            f"email_resolve_invalid_input message_id={mid or None} company_id={cid or None}"
        )
        return (
            "pending_tenant",
            None,
            "UNKNOWN",
            0.0,
            [],
            {"category": "UNKNOWN", "state": "EMAIL_RESOLVE"},
            None,
        )

    pending = get_pending_email(memory=memory, message_id=mid)
    if not pending:
        logger.info(f"email_resolve_missing_pending message_id={mid}")
        return (
            "pending_tenant",
            None,
            "UNKNOWN",
            0.0,
            [],
            {"category": "UNKNOWN", "state": "EMAIL_RESOLVE"},
            None,
        )

    tenant, valid = validate_and_get_tenant(cid)
    if tenant is None:
        logger.info(
            f"email_resolve_invalid_tenant message_id={mid} company_id={cid} valid={valid}"
        )

        intent = pending.get("intent", "UNKNOWN")
        confidence = float(pending.get("confidence", 0.0) or 0.0)
        handoff_summary = pending.get("handoff_summary") or {
            "category": intent,
            "state": "EMAIL_INGEST",
        }
        internal_tags = pending.get("internal_tags", [])

        return (
            "pending_tenant",
            None,
            intent,
            confidence,
            internal_tags,
            handoff_summary,
            None,
        )

    intent = pending.get("intent", "UNKNOWN")
    confidence = float(pending.get("confidence", 0.0) or 0.0)
    handoff_summary = pending.get("handoff_summary") or {
        "category": intent,
        "state": "EMAIL_INGEST",
    }

    ensure_internal_tags(handoff_summary)
    internal_tags = get_internal_tags(handoff_summary)

    if intent == "VPN_ISSUE":
        jira_payload_preview, labels = build_vpn_payload_preview(
            session_id=mid,
            tenant=tenant,
            handoff_summary=handoff_summary,
        )
    else:
        jira_payload_preview, labels = build_generic_payload_preview(
            correlation_id=mid,
            tenant=tenant,
            handoff_summary=handoff_summary,
        )

    clear_pending_email(memory=memory, message_id=mid)

    logger.info(
        f"email_resolved message_id={mid} tenant_id={tenant.tenant_id} "
        f"intent={intent} conf={confidence:.2f} labels={labels}"
    )

    return (
        "processed",
        tenant.tenant_id,
        intent,
        confidence,
        internal_tags,
        handoff_summary,
        jira_payload_preview,
    )
