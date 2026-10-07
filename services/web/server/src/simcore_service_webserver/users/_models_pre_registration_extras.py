"""Typed helpers for the ``extras`` JSONB column on ``users_pre_registration_details``.

Writers must go through the models/builders below (never free-form string keys) so the
stored JSON stays consistent and typos are caught early.

Known top-level keys (see ``PreRegistrationExtraKey``)
------------------------------------------------------
- **invitation**: stored when an approval generates an invitation link; also carries the
  reviewer's ``send_mail`` decision (for a new user the approval audit lives here).
- **approval**: audit of an approval that generates no invitation, i.e. granting an
  already-registered user access to another product (``extra_credits_in_usd`` and the
  ``send_mail`` decision, i.e. whether the reviewer chose to notify the user).
- **rejection**: audit of the rejection itself (the ``send_mail`` decision, i.e. whether the
  reviewer chose to notify the user).
- **recovery**: written by data-reconciliation / migration scripts.
- **product_move**: audit trail when a PO moves the request to another product.
- *form fields*: arbitrary key/value pairs from the original request form (not part of the
  enum; kept as-is inside ``extras``).
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal

from models_library.api_schemas_invitations.invitations import ApiInvitationContent
from pydantic import BaseModel, ConfigDict, PositiveInt


class PreRegistrationExtraKey(StrEnum):
    """Top-level ``extras`` keys that have a known structure"""

    INVITATION = "invitation"
    APPROVAL = "approval"
    REJECTION = "rejection"
    RECOVERY = "recovery"
    PRODUCT_MOVE = "product_move"


class ApprovalExtrasEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    send_mail: bool
    extra_credits_in_usd: PositiveInt | None = None


class RejectionExtrasEntry(BaseModel):
    model_config = ConfigDict(frozen=True)

    send_mail: bool


class InvitationExtrasEntry(ApiInvitationContent):
    model_config = ConfigDict(extra="forbid")

    send_mail: bool


type PreRegistrationExtrasPatch = dict[PreRegistrationExtraKey, Any]


def create_approval_extras(
    *,
    send_mail: bool,
    extra_credits_in_usd: PositiveInt | None = None,
) -> PreRegistrationExtrasPatch:
    entry = ApprovalExtrasEntry(send_mail=send_mail, extra_credits_in_usd=extra_credits_in_usd)
    return {PreRegistrationExtraKey.APPROVAL: entry.model_dump(mode="json", exclude_none=True)}


def create_invitation_extras(
    invitation: ApiInvitationContent,
    *,
    send_mail: bool,
) -> PreRegistrationExtrasPatch:
    entry = InvitationExtrasEntry.model_validate({**invitation.model_dump(mode="json"), "send_mail": send_mail})
    return {PreRegistrationExtraKey.INVITATION: entry.model_dump(mode="json")}


def create_rejection_extras(*, send_mail: bool) -> PreRegistrationExtrasPatch:
    return {PreRegistrationExtraKey.REJECTION: RejectionExtrasEntry(send_mail=send_mail).model_dump(mode="json")}


class ExtrasAuditEntry(BaseModel):
    source: str
    confidence: Literal["high", "medium", "low"]
    executed_at: datetime
    notes: str

    @classmethod
    def create_now(
        cls,
        *,
        source: str,
        notes: str,
        confidence: Literal["high", "medium", "low"] = "high",
    ) -> "ExtrasAuditEntry":
        return cls(
            source=source,
            confidence=confidence,
            executed_at=datetime.now(tz=UTC),
            notes=notes,
        )


def merge_audit_entry_into_extras(
    *,
    current_extras: dict[str, Any] | None,
    key: PreRegistrationExtraKey,
    entry: ExtrasAuditEntry,
) -> dict[str, Any]:
    extras: dict[str, Any] = dict(current_extras or {})
    new_payload = entry.model_dump(mode="json")

    previous_value = extras.get(key)
    if previous_value is None:
        extras[key] = new_payload
    elif isinstance(previous_value, list):
        extras[key] = [*previous_value, new_payload]
    else:
        extras[key] = [previous_value, new_payload]

    return extras
