import re
from typing import Optional

from app.schemas.chat_models import VpnOS, VpnSymptom


def extract_os(text: str) -> Optional[VpnOS]:
    t = text.lower()

    if any(x in t for x in ["windows", "win11", "win 11", "win10", "win 10", "win7", "win 7"]):
        return VpnOS.WINDOWS

    if any(x in t for x in ["mac", "macos", "osx", "os x", "macbook"]):
        return VpnOS.MAC

    if any(x in t for x in ["linux", "ubuntu", "debian", "fedora", "arch"]):
        return VpnOS.LINUX

    if any(x in t for x in ["android", "iphone", "ios", "ipad"]):
        return VpnOS.OTHER

    return None


def extract_client(text: str) -> Optional[str]:
    """
    Best-effort VPN client extraction.
    Returns a normalized client name or None.
    """
    t = text.lower()

    if "anyconnect" in t:
        return "AnyConnect"

    if "globalprotect" in t or "global protect" in t:
        return "GlobalProtect"

    if "forticlient" in t or "forti" in t:
        return "FortiClient"

    return None


def extract_symptom(text: str) -> Optional[VpnSymptom]:
    """
    Extract high-level VPN symptom category.
    """
    t = text.lower()

    if any(x in t for x in ["can't connect", "cannot connect", "won't connect", "fails to connect"]):
        return VpnSymptom.CANNOT_CONNECT

    if any(x in t for x in ["connects but", "connected but", "no access", "can't access internal", "cannot access internal"]):
        return VpnSymptom.CONNECTS_NO_ACCESS

    if any(x in t for x in ["disconnects", "drops", "keeps disconnecting", "unstable"]):
        return VpnSymptom.DISCONNECTS

    return None


def extract_error_code(text: str) -> Optional[str]:
    """
    Captures:
    - "619"
    - "error 619"
    - "error code: 809"
    Also supports a few keyword-style "codes" for MVP.
    """
    t = text.lower()

    # 3-4 digit code patterns
    m = re.search(
        r"\b(?:error\s*code\s*[:\-]?\s*|error\s*[:\-]?\s*|code\s*[:\-]?\s*)?(\d{3,4})\b",
        t,
    )
    if m:
        return m.group(1)

    # Keyword-style cases (keep tiny for MVP)
    if any(k in t for k in ["certificate", "cert", "expired certificate"]):
        return "CERTIFICATE"

    if any(k in t for k in ["timeout", "timed out"]):
        return "TIMEOUT"

    if any(k in t for k in ["auth failed", "authentication failed", "login failed", "invalid credentials"]):
        return "AUTH_FAILED"

    return None


def looks_like_success(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in ["works now","fixed","resolved","it works","connected","success","working now"])

def looks_like_failure(text: str) -> bool:
    t = text.lower()
    return any(k in t for k in ["still","doesn't","doesnt","not working","failed","same error","nope","no"])
