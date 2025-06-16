# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import string

import pytest
from hypothesis import given
from hypothesis import strategies as st
from passlib.hash import sha256_crypt
from simcore_service_webserver.security import security_service


def test_encrypt_password_returns_string():
    assert isinstance(security_service.encrypt_password("password"), str)


def test_encrypt_password_returns_valid_sha256_hash():
    password = "password"
    hashed_password = security_service.encrypt_password(password)
    assert security_service.check_password(password, hashed_password)


def test_encrypt_password_raises_type_error_for_non_string_input():
    with pytest.raises(TypeError):
        security_service.encrypt_password(123)


@given(
    st.text(
        alphabet=string.ascii_letters + string.digits + string.punctuation, min_size=1
    )
)
@pytest.mark.filterwarnings(
    "ignore:passing settings to"
)  # DeprecationWarning of sha256_crypt.hash
def test_encrypt_decrypt_deprecated_and_new_method_return_same_values(password: str):
    salt = "salt"  # Use a fixed salt value for consistent hash values

    hashed_password_new = sha256_crypt.using(rounds=1000).hash(password, salt=salt)
    hashed_password_old = sha256_crypt.hash(password, rounds=1000, salt=salt)
    assert hashed_password_new == hashed_password_old

    assert security_service.check_password(password, hashed_password_new)
