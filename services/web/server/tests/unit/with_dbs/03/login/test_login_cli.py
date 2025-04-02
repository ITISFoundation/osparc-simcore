from io import StringIO

import simcore_service_webserver.login.cli
from pytest_mock import MockerFixture
from simcore_service_webserver.login.cli import invitations
from yarl import URL


def test_invitations(mocker: MockerFixture):
    base_url = "http://example.com"
    issuer_email = "test@example.com"
    trial_days = 7
    user_id = 42
    num_codes = 3
    code_length = 10

    # Spy on generate_password to track generated codes
    spy_generate_password = mocker.spy(
        simcore_service_webserver.login.cli, "generate_password"
    )

    # Mock sys.stdout to capture printed output
    mock_stdout = StringIO()
    mocker.patch("sys.stdout", new=mock_stdout)

    invitations(
        base_url=base_url,
        issuer_email=issuer_email,
        trial_days=trial_days,
        user_id=user_id,
        num_codes=num_codes,
        code_length=code_length,
    )

    output = mock_stdout.getvalue()

    # Assert that the correct number of passwords were generated
    assert spy_generate_password.call_count == num_codes

    # Collect generated codes
    generated_codes = spy_generate_password.spy_return_list

    # Assert that the invitation links are correctly generated
    for i, code in enumerate(generated_codes, start=1):
        expected_url = URL(base_url).with_fragment(f"/registration/?invitation={code}")
        assert f"{i:2d}. {expected_url}" in output
