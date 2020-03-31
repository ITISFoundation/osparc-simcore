from simcore_service_api_gateway.auth_security import verify_password, get_password_hash


def test_has_password():
    hashed_pass = get_password_hash("secret")
    assert hashed_pass != "secret"
    assert verify_password("secret", hashed_pass)
