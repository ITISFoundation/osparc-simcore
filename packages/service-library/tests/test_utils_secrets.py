# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from uuid import uuid4

import pytest
from pydantic import ValidationError
from servicelib.utils_secrets import (
    _MIN_SECRET_NUM_BYTES,
    _PLACEHOLDER,
    MIN_PASSCODE_LENGTH,
    MIN_PASSWORD_LENGTH,
    are_secrets_equal,
    generate_passcode,
    generate_password,
    generate_token_secret_key,
    mask_sensitive_data,
    secure_randint,
)


def test_generate_password():
    # NOT idempotent
    assert generate_password() != generate_password()

    # Avoids '"' so that we can save quoted passwords in envfiles without complications
    password = generate_password()
    assert '"' not in password

    # min lenght
    password = generate_password(length=MIN_PASSWORD_LENGTH + 2)
    assert len(password) == MIN_PASSWORD_LENGTH + 2

    password = generate_password(length=2)
    assert len(password) == MIN_PASSWORD_LENGTH

    password = generate_password(length=0)
    assert len(password) == MIN_PASSWORD_LENGTH


def test_generate_passcode():
    # NOT idempotent
    assert generate_passcode() != generate_passcode()

    # Avoids '"' so that we can save quoted passwords in envfiles without complications
    passcode = generate_passcode()
    assert '"' not in passcode

    # min lenght
    passcode = generate_passcode(number_of_digits=MIN_PASSCODE_LENGTH + 2)
    assert len(passcode) == MIN_PASSCODE_LENGTH + 2

    passcode = generate_passcode(number_of_digits=2)
    assert len(passcode) == MIN_PASSCODE_LENGTH

    passcode = generate_passcode(number_of_digits=0)
    assert len(passcode) == MIN_PASSCODE_LENGTH

    # passcode is a number
    assert int(generate_passcode()) >= 0


def test_compare_secrets():
    passcode = generate_passcode(100)
    assert not are_secrets_equal(got="foo", expected=passcode)
    assert are_secrets_equal(got=passcode, expected=passcode)


def test_generate_token_secrets():
    secret_key = generate_token_secret_key()
    assert len(secret_key) == 2 * _MIN_SECRET_NUM_BYTES


@pytest.mark.parametrize("start, end", [(1, 2), (1, 10), (99, 100)])
async def test_secure_randint(start: int, end: int):
    random_number = secure_randint(start, end)
    assert start <= random_number <= end


async def test_secure_randint_called_with_wrong_tupes():
    with pytest.raises(ValidationError):
        secure_randint(1.1, 2)


def test_mask_sensitive_data():
    sensitive_data = {
        "username": "john_doe",
        "password": "sensitive_password",
        "details": {
            "secret_key": "super_secret_key",
            "nested": {"nested_password": "nested_sensitive_password"},
        },
        "credit-card": "12345",
        uuid4(): object(),
    }

    masked_data = mask_sensitive_data(
        sensitive_data, extra_sensitive_keywords={"credit-card"}
    )

    assert masked_data == {
        "username": "john_doe",
        "password": _PLACEHOLDER,
        "details": {
            "secret_key": _PLACEHOLDER,
            "nested": {"nested_password": _PLACEHOLDER},
        },
        "credit-card": _PLACEHOLDER,
    }
