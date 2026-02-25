import ipaddress
import urllib.parse
from email.utils import formataddr, parseaddr
from typing import Final

# Common email parts
NO_REPLY_LOCAL: Final[str] = "no-reply"


def is_ip_address(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def redact_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)

    if not parsed.password:
        return url

    new_netloc = f"{parsed.username}:***@{parsed.hostname}" if parsed.username else f":***@{parsed.hostname}"

    if parsed.port:
        new_netloc = f"{new_netloc}:{parsed.port}"

    return urllib.parse.urlunparse(
        (
            parsed.scheme,
            new_netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            parsed.fragment,
        )
    )


def replace_email_parts(original_email: str, new_local: str, new_display_name: str | None = None) -> str:
    """
    Replace the local part and optionally the display name of an email string.

    Preserves the domain. If new_display_name is not provided, auto-generates from new_local
    if the original email had a display name.

    Args:
        original_email: Original email, e.g., "Support Team <support@example.com>"
        new_local: New local part, e.g., "no-reply" or "alerts"
        new_display_name: Optional custom display name. If not provided and original had a name,
          auto-generates from new_local. If original had no name, remains empty.

    Returns:
        Transformed email, e.g., "No Reply <no-reply@example.com>"
    """
    name, addr = parseaddr(original_email)

    try:
        _, domain = addr.split("@")
    except ValueError as exc:
        msg = f"Invalid email address: {addr}"
        raise ValueError(msg) from exc

    # Determine display name: use provided value, auto-generate, or empty
    if new_display_name is not None:
        new_name = new_display_name
    elif name:
        new_name = new_local.replace("-", " ").title()
    else:
        new_name = ""

    new_addr = f"{new_local}@{domain}"

    return formataddr((new_name, new_addr))
