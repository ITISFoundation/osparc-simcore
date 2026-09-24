# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import hashlib
import hmac

from simcore_service_webserver.cli import main
from typer.testing import CliRunner


def test_main_cli():
    cli_runner = CliRunner()
    result = cli_runner.invoke(main, "--help")
    assert "otp-to-hmac" in result.stdout
    assert "settings" in result.stdout
    assert "run" in result.stdout
    assert result.exit_code == 0

    result = cli_runner.invoke(main, ["settings", "--help"])
    assert result.exit_code == 0

    result = cli_runner.invoke(main, ["run", "--help"])
    assert result.exit_code == 0


def test_otp_to_hmac_accepts_explicit_secret_key():
    cli_runner = CliRunner()
    otp = "123456"
    secret_key = "REPLACE_ME_with_result__Fernet_generate_key="  # noqa: S105

    result = cli_runner.invoke(
        main,
        ["otp-to-hmac", otp, "--session-secret-key", secret_key],
    )

    expected = hmac.new(
        key=secret_key.encode(),
        msg=otp.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()

    assert result.exit_code == 0
    assert result.stdout.strip() == expected


def test_otp_to_hmac_reads_secret_key_from_env():
    cli_runner = CliRunner()
    otp = "654321"
    secret_key = "REPLACE_ME_with_result__Fernet_generate_key="  # noqa: S105

    result = cli_runner.invoke(
        main,
        ["otp-to-hmac", otp],
        env={"WEBSERVER_SESSION_SECRET_KEY": secret_key},
    )

    expected = hmac.new(
        key=secret_key.encode(),
        msg=otp.encode(),
        digestmod=hashlib.sha256,
    ).hexdigest()

    assert result.exit_code == 0
    assert result.stdout.strip() == expected
