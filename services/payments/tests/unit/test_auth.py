from simcore_service_payments.core.settings import ApplicationSettings
from simcore_service_payments.services.auth import authenticate_user


def test_authenticate_user_boundary_collision_prevention(auth_settings: ApplicationSettings):
    # regression: authenticate_user used to compare username+password as a single
    # concatenated string, so this pair -- a different split of the same string --
    # used to authenticate as the valid ("testuser", "testpass") credentials.
    # Credential semantics themselves are tested in servicelib's test_utils_secrets.py
    assert authenticate_user("test", "usertestpass", auth_settings) is False
    assert authenticate_user("testuser", "testpass", auth_settings) is True
