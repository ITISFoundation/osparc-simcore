# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from faker import Faker
from pydantic import TypeAdapter, ValidationError
from pytest_simcore.helpers.faker_factories import random_phone_number
from simcore_service_webserver.users._controller.rest._rest_schemas import (
    MyPhoneRegister,
    PhoneNumberStr,
)


@pytest.mark.parametrize(
    "phone",
    [
        "+41763456789",
        "+19104630364",
        "+1 301-304-4567",
        "+41763456686",
        "+19104630873",
        "+19104630424",
        "+34 950 453 772",
        "+19104630700",
        "+13013044719",
    ],
)
def test_valid_phone_numbers(phone: str):
    # This test is used to tune options of PhoneNumberValidator
    assert MyPhoneRegister.model_validate({"phone": phone}).phone == TypeAdapter(
        PhoneNumberStr
    ).validate_python(phone)


def test_random_phone_number():
    # This test is used to tune options of PhoneNumberValidator
    for _ in range(10):
        phone = random_phone_number(Faker(seed=42))
        assert MyPhoneRegister.model_validate({"phone": phone}).phone == TypeAdapter(
            PhoneNumberStr
        ).validate_python(phone)


@pytest.mark.parametrize(
    "phone",
    [
        "+41763456789",
        "+41 76 345 67 89",
        "tel:+41-76-345-67-89",
    ],
    ids=["E.164", "INTERNATIONAL", "RFC3966"],
)
def test_autoformat_phone_number_to_e164(phone: str):
    # This test is used to tune options of PhoneNumberValidator formatting to E164
    assert TypeAdapter(PhoneNumberStr).validate_python(phone) == "+41763456789"


@pytest.mark.parametrize(
    "phone",
    ["41763456789", "+09104630364", "+1 111-304-4567"],
)
def test_invalid_phone_numbers(phone: str):
    # This test is used to tune options of PhoneNumberValidator
    with pytest.raises(ValidationError):
        MyPhoneRegister.model_validate({"phone": phone})
