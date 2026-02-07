from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple


@dataclass(frozen=True)
class TenantConfig:
    tenant_id: str
    display_name: str

    jira_project_key: str
    jira_issue_type: str

    # Tenant default labels always added
    default_labels: Tuple[str, ...] = ()

    # Optional
    component: Optional[str] = None

    # internal-tag -> jira labels mapping (per tenant)
    # Example: "stability" -> ("vpn-disconnect",)
    label_map: Dict[str, Tuple[str, ...]] = None  # type: ignore[assignment]


TENANTS: Dict[str, TenantConfig] = {
    "ness_bank": TenantConfig(
        tenant_id="ness_bank",
        display_name="Ness Bank (Fake)",
        jira_project_key="BANK",
        jira_issue_type="Incident",
        default_labels=("it-support", "vpn"),
        component="Network",
        label_map={
            # ===== VPN domain =====
            "vpn": ("vpn",),

            # Problem class
            "connectivity": ("vpn-connectivity",),
            "access": ("vpn-access",),
            "stability": ("vpn-disconnect",),

            # Signals
            "certificate": ("cert",),
            "auth_failed": ("auth",),
            "timeout": ("timeout",),

            # Process
            "escalated": ("escalated",),

            # Error codes (examples)
            "error_619": ("error-619",),
            "error_809": ("error-809",),
            "error_812": ("error-812",),

            # ===== Generic (pre-LLM) domains =====
            "password": ("password-reset",),
            "email": ("email-issue",),
            "general": ("it-general",),
            "unknown": ("needs-triage",),
        },
    ),
    "ness_auto": TenantConfig(
        tenant_id="ness_auto",
        display_name="Ness Auto (Fake)",
        jira_project_key="AUTO",
        jira_issue_type="Service Request",
        default_labels=("helpdesk", "vpn"),
        component="IT",
        label_map={
            # ===== VPN domain =====
            "vpn": ("vpn",),

            # Problem class (different naming style)
            "connectivity": ("network", "vpn-connection"),
            "access": ("access", "vpn-access"),
            "stability": ("unstable", "vpn-drop"),

            # Signals (different naming style)
            "certificate": ("cert-issue",),
            "auth_failed": ("login", "auth"),
            "timeout": ("timeout",),

            # Process
            "escalated": ("handoff",),

            # Error codes (examples)
            "error_619": ("err-619",),
            "error_809": ("err-809",),
            "error_812": ("err-812",),

            # ===== Generic (pre-LLM) domains =====
            "password": ("pwd", "reset"),
            "email": ("mail", "outlook"),
            "general": ("general",),
            "unknown": ("triage",),
        },
    ),
}


def list_tenant_ids() -> Tuple[str, ...]:
    return tuple(TENANTS.keys())


def is_valid_tenant_id(tenant_id: str) -> bool:
    return tenant_id in TENANTS


def get_tenant_or_none(tenant_id: Optional[str]) -> Optional[TenantConfig]:
    if not tenant_id:
        return None
    return TENANTS.get(tenant_id)
