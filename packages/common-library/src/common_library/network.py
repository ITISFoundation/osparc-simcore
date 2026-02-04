import ipaddress
import urllib.parse
from email.utils import formataddr, parseaddr
from typing import Final

# Common email locals
NO_REPLY_DISPLAY_NAME: Final[str] = "No Reply"
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


def replace_email_local(email_str: str, new_local: str, new_display_name: str | None = None) -> str:
    """
    Replace the local part of an email string to use a new local part, preserving the domain and display name.

    Args:
        email_str: Original email, e.g., "Support Team <support@example.com>"
        new_local: New local part, e.g., "no-reply" or "alerts"
        new_display_name: Optional custom display name. If not provided, auto-generates from new_local
          if original had a name

    Returns:
        Transformed email, e.g., "No Reply <no-reply@example.com>"
    """
    name, addr = parseaddr(email_str)

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
