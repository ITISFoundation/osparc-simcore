import pytest
from models_library.notifications.rpc import (
    Addressing,
    EmailAddressing,
    EmailContact,
    EmailContent,
    EmailMessage,
    Message,
    SmsAddressing,
    SmsContact,
    SmsContent,
    SmsMessage,
)
from pydantic import TypeAdapter, ValidationError


def test_email_message_backward_compatible_without_channel_key():
    # NOTE: existing payloads for email did not (and still don't need to) include a "channel" key
    email_message = TypeAdapter(EmailMessage).validate_python(
        {
            "addressing": {
                "to": [{"name": "John Doe", "email": "john@example.com"}],
            },
            "content": {"subject": "Welcome!", "body_text": "Welcome to osparc!"},
        }
    )
    assert email_message.channel == "email"


def test_message_discriminated_union_selects_email():
    message = TypeAdapter(Message).validate_python(
        {
            "channel": "email",
            "addressing": {
                "to": [{"name": "John Doe", "email": "john@example.com"}],
            },
            "content": {"subject": "Welcome!", "body_text": "Welcome to osparc!"},
        }
    )
    assert isinstance(message, EmailMessage)


def test_message_discriminated_union_selects_sms():
    message = TypeAdapter(Message).validate_python(
        {
            "channel": "sms",
            "addressing": {"to": [{"phone_number": "+41791234567"}]},
            "content": {"body": "Your code is 123456"},
        }
    )
    assert isinstance(message, SmsMessage)


def test_message_discriminated_union_requires_channel_key():
    with pytest.raises(ValidationError, match="union_tag_not_found"):
        TypeAdapter(Message).validate_python(
            {
                "addressing": {"to": [{"phone_number": "+41791234567"}]},
                "content": {"body": "Your code is 123456"},
            }
        )


def test_addressing_union_resolves_by_structure():
    email_addressing = TypeAdapter(Addressing).validate_python(
        {"to": [{"name": "John Doe", "email": "john@example.com"}]}
    )
    assert isinstance(email_addressing, EmailAddressing)

    sms_addressing = TypeAdapter(Addressing).validate_python({"to": [{"phone_number": "+41791234567"}]})
    assert isinstance(sms_addressing, SmsAddressing)


@pytest.mark.parametrize(
    "phone_number",
    ["+41791234567", "+15551234567"],
)
def test_sms_contact_accepts_e164_phone_numbers(phone_number: str):
    assert SmsContact(phone_number=phone_number).phone_number == phone_number


@pytest.mark.parametrize(
    "phone_number",
    ["0791234567", "41791234567", "+0791234567", "not-a-number", ""],
)
def test_sms_contact_rejects_non_e164_phone_numbers(phone_number: str):
    with pytest.raises(ValidationError):
        SmsContact(phone_number=phone_number)


def test_sms_message_serialization_round_trip():
    message = SmsMessage(
        addressing=SmsAddressing(to=[SmsContact(phone_number="+41791234567")]),
        content=SmsContent(body="Your code is 123456"),
    )
    payload = message.model_dump(mode="json")
    assert payload["channel"] == "sms"

    reloaded = SmsMessage.model_validate(payload)
    assert reloaded == message


def test_email_message_serialization_round_trip():
    message = EmailMessage(
        addressing=EmailAddressing(to=[EmailContact(name="John Doe", email="john@example.com")]),
        content=EmailContent(subject="Welcome!", body_text="Welcome to osparc!"),
    )
    payload = message.model_dump(mode="json")
    assert payload["channel"] == "email"

    reloaded = EmailMessage.model_validate(payload)
    assert reloaded == message
