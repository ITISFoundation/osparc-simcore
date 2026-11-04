from pydantic import EmailStr, Field

from .user_preferences import FrontendUserPreference


class AllowMetricsCollectionFrontendUserPreference(FrontendUserPreference):
    preference_identifier: str = "allowMetricsCollection"
    value: bool = True


class InvoiceEmailRecipientsFrontendUserPreference(FrontendUserPreference):
    preference_identifier: str = "invoiceEmailRecipients"
    value: list[EmailStr] = Field(default_factory=list)
