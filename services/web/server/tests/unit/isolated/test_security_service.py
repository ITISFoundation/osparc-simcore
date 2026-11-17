# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import string

import pytest
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id
from hypothesis import given
from hypothesis import strategies as st
from passlib.hash import sha256_crypt
from simcore_service_webserver.security import security_service


def test_encrypt_password_returns_string():
    assert isinstance(security_service.encrypt_password("password"), str)


def test_encrypt_password_returns_verifiable_hash():
    password = "password"  # dummy test password  # noqa: S105
    hashed_password = security_service.encrypt_password(password)
    assert security_service.check_password(password, hashed_password)


def test_encrypt_password_uses_argon2id():
    assert security_service.encrypt_password("password").startswith("$argon2id$")


def test_check_password_rejects_wrong_password():
    hashed_password = security_service.encrypt_password("password")
    assert not security_service.check_password("other", hashed_password)


def test_password_needs_rehash():
    legacy_hash = sha256_crypt.using(rounds=1000).hash("password")
    assert security_service.check_password("password", legacy_hash)
    assert security_service.password_needs_rehash(legacy_hash)

    assert not security_service.password_needs_rehash(security_service.encrypt_password("password"))

    weaker_params_hash = Argon2id(
        salt=b"0123456789abcdef", length=32, iterations=1, lanes=1, memory_cost=19 * 1024
    ).derive_phc_encoded(b"password")
    assert security_service.password_needs_rehash(weaker_params_hash)


def test_encrypt_password_raises_type_error_for_non_string_input():
    with pytest.raises(TypeError):
        security_service.encrypt_password(123)


@given(st.text(alphabet=string.ascii_letters + string.digits + string.punctuation, min_size=1))
@pytest.mark.filterwarnings("ignore:passing settings to")  # DeprecationWarning of sha256_crypt.hash
def test_encrypt_decrypt_deprecated_and_new_method_return_same_values(password: str):
    salt = "salt"  # Use a fixed salt value for consistent hash values

    hashed_password_new = sha256_crypt.using(rounds=1000).hash(password, salt=salt)
    hashed_password_old = sha256_crypt.hash(password, rounds=1000, salt=salt)
    assert hashed_password_new == hashed_password_old

    assert security_service.check_password(password, hashed_password_new)
