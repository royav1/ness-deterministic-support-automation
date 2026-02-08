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
from app.flows.vpn.vpn_nlp import extract_os, extract_client, extract_symptom, extract_error_code


# ---------------------------------------------------------------------
# Tenant inference from recipient email (realistic simulation)
# ---------------------------------------------------------------------

TENANT_EMAIL_HINTS = {
    "ness_bank": ["bank", "ness_bank"],
    "ness_auto": ["auto", "ness_auto"],
}


def infer_tenant_id_from_to_email(to_email: str) -> Optional[str]:
    """
    Infer tenant from recipient email.

    Priority:
    1) Plus-addressing: support+ness_bank@company.com
    2) Keyword hints in mailbox/domain

    This simulates real IT support inbox routing without real mailboxes.
    """
    if not to_email:
        return None

    email = to_email.lower().strip()

    # ---- Option 1: plus addressing (preferred, realistic) ----
    # Example: support+ness_bank@company.com
    if "+" in email:
        local_part = email.split("@", 1)[0]
        if "+" in local_part:
            _, tag = local_part.split("+", 1)
            tag = tag.strip()
            if tag:
                return tag

    # ---- Option 2: keyword hints fallback ----
    for tenant_id, hints in TENANT_EMAIL_HINTS.items():
        if any(h in email for h in hints):
            return tenant_id

    return None


# ---------------------------------------------------------------------
# Handoff summary builders
# ---------------------------------------------------------------------

def build_vpn_handoff_summary_from_email(req: EmailIngestRequest) -> Dict[str, Any]:
    text = f"{req.subject}\n{req.body}".strip()

    os_guess = extract_os(text)
    client_guess = extract_client(text)
    symptom_guess = extract_symptom(text)
    code_guess = extract_error_code(text)

    return {
        "category": "VPN_ISSUE",
        "state": "EMAIL_INGEST",
        "os": os_guess.value if os_guess else None,
        "client": client_guess,
        "symptom": symptom_guess.value if symptom_guess else None,
        "error_code": code_guess,
        "attempt_count": 0,
        "steps_given": [],
        "email": {
            "message_id": req.message_id,
            "from": req.from_email,
            "to": req.to_email,
            "subject": req.subject,
        },
    }


def build_generic_handoff_summary_from_email(
    req: EmailIngestRequest, intent: Intent
) -> Dict[str, Any]:
    return {
        "category": intent,
        "state": "EMAIL_INGEST",
        "email": {
            "message_id": req.message_id,
            "from": req.from_email,
            "to": req.to_email,
            "subject": req.subject,
        },
        "body": req.body,
    }


# ---------------------------------------------------------------------
# Main processor
# ---------------------------------------------------------------------

def process_email_to_jira_preview(
    *,
    memory: Any,
    req: EmailIngestRequest,
    x_company_id: Optional[str],
    logger: Any,
) -> Tuple[str, Optional[str], Intent, float, List[str], Dict[str, Any], Optional[Dict[str, Any]]]:
    """
    Returns:
      (status, tenant_id, intent, confidence, internal_tags, handoff_summary, jira_payload_preview)

    status: processed | pending_tenant
    """

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
    if intent == "VPN_ISSUE":
        handoff_summary = build_vpn_handoff_summary_from_email(req)
    else:
        handoff_summary = build_generic_handoff_summary_from_email(req, intent)

    ensure_internal_tags(handoff_summary)
    internal_tags = get_internal_tags(handoff_summary)

    # ---- Missing tenant → pending ----
    if tenant is None:
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
