from enum import StrEnum
from typing import Final

ALLOWED_HEADERS: Final[frozenset[str]] = frozenset(
    {
        # AWS SES routing/configuration
        "x-ses-tenant",
        "x-ses-configuration-set",
        "x-ses-source-arn",
        "x-ses-from-arn",
        "x-ses-return-path-arn",
        # Delivery metadata (safe, non-structural)
        "return-path",
        "x-mailer",
        "x-priority",
        "precedence",
        "list-unsubscribe",
        "list-unsubscribe-post",
    }
)


class EmailProtocol(StrEnum):
    UNENCRYPTED = "UNENCRYPTED"
    TLS = "TLS"
    STARTTLS = "STARTTLS"
