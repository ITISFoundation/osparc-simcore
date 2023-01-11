from servicelib.utils_secrets import MIN_PASSWORD_LENGTH, generate_password


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
