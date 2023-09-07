# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

from servicelib.utils_secrets import (
    MIN_PASSCODE_LENGTH,
    MIN_PASSWORD_LENGTH,
    compare_secrets,
    generate_passcode,
    generate_password,
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
    assert not compare_secrets(got="foo", expected=passcode)
    assert compare_secrets(got=passcode, expected=passcode)
