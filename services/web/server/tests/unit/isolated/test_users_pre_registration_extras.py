# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=protected-access

from datetime import UTC, datetime

import pytest
from models_library.api_schemas_invitations.invitations import ApiInvitationContent
from pydantic import ValidationError
from simcore_service_webserver.users._models_pre_registration_extras import (
    ExtrasAuditEntry,
    InvitationExtrasEntry,
    PreRegistrationExtraKey,
    create_approval_extras,
    create_invitation_extras,
    create_rejection_extras,
    merge_audit_entry_into_extras,
)


def test_extra_key_values_match_documented_json_keys():
    assert {key.value for key in PreRegistrationExtraKey} == {
        "invitation",
        "approval",
        "rejection",
        "recovery",
        "product_move",
    }


def test_create_approval_extras_omits_unset_credits():
    assert create_approval_extras(send_mail=True) == {"approval": {"send_mail": True}}


def test_create_approval_extras_with_credits():
    assert create_approval_extras(send_mail=False, extra_credits_in_usd=100) == {
        "approval": {"send_mail": False, "extra_credits_in_usd": 100}
    }


def test_create_rejection_extras():
    assert create_rejection_extras(send_mail=True) == {"rejection": {"send_mail": True}}


@pytest.fixture
def api_invitation_content() -> ApiInvitationContent:
    return ApiInvitationContent(
        issuer="123",
        guest="guest@example.com",
        trial_account_days=7,
        product="osparc",
        created=datetime.now(tz=UTC),
    )


def test_create_invitation_extras_serializes_invitation_and_decision(
    api_invitation_content: ApiInvitationContent,
):
    patch = create_invitation_extras(invitation=api_invitation_content, send_mail=True)

    assert list(patch) == [PreRegistrationExtraKey.INVITATION]
    entry = patch[PreRegistrationExtraKey.INVITATION]
    assert entry["send_mail"] is True
    assert entry["guest"] == "guest@example.com"
    assert entry["trial_account_days"] == 7
    # JSON-serializable (stored in a JSONB column)
    assert isinstance(entry["created"], str)
    InvitationExtrasEntry.model_validate(entry)  # round-trip


def test_create_invitation_extras_rejects_unknown_fields(api_invitation_content: ApiInvitationContent):
    with pytest.raises(ValidationError):
        InvitationExtrasEntry.model_validate(
            {**api_invitation_content.model_dump(mode="json"), "send_mail": True, "typo_field": 1},
        )


def test_merge_audit_entry_creates_key_when_missing():
    entry = ExtrasAuditEntry.create_now(source="po_center:move_product", notes="moved A -> B")
    merged = merge_audit_entry_into_extras(current_extras=None, key=PreRegistrationExtraKey.PRODUCT_MOVE, entry=entry)

    assert list(merged) == [PreRegistrationExtraKey.PRODUCT_MOVE]
    assert merged[PreRegistrationExtraKey.PRODUCT_MOVE]["notes"] == "moved A -> B"


def test_merge_audit_entry_appends_to_history():
    entry = ExtrasAuditEntry.create_now(source="po_center:move_product", notes="moved B -> C")
    previous = {
        PreRegistrationExtraKey.PRODUCT_MOVE: {
            "source": "po_center:move_product",
            "confidence": "high",
            "executed_at": "2026-01-01T00:00:00Z",
            "notes": "moved A -> B",
        }
    }
    merged = merge_audit_entry_into_extras(
        current_extras=previous, key=PreRegistrationExtraKey.PRODUCT_MOVE, entry=entry
    )

    history = merged[PreRegistrationExtraKey.PRODUCT_MOVE]
    assert isinstance(history, list)
    assert [e["notes"] for e in history] == ["moved A -> B", "moved B -> C"]


def test_merge_audit_entry_does_not_touch_other_keys():
    entry = ExtrasAuditEntry.create_now(source="x", notes="n")
    previous = {PreRegistrationExtraKey.APPROVAL: {"send_mail": True}, "firstName": "Sheldon"}
    merged = merge_audit_entry_into_extras(current_extras=previous, key=PreRegistrationExtraKey.RECOVERY, entry=entry)

    assert merged[PreRegistrationExtraKey.APPROVAL] == {"send_mail": True}
    assert merged["firstName"] == "Sheldon"
    assert PreRegistrationExtraKey.RECOVERY in merged
