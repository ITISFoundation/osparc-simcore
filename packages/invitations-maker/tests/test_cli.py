# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import os

from invitations_maker.cli import main
from typer.testing import CliRunner


def test_it(cli_runner: CliRunner):

    result = cli_runner.invoke(main, "--help")
    assert result.exit_code == os.EX_OK

    result = cli_runner.invoke(main, "--help")
    assert result.exit_code == os.EX_OK

    # export INVITATIONS_MAKER_SECRET_KEY=$(invitations-maker generate-key)
    # export INVITATIONS_MAKER_OSPARC_URL=https://myosparc.com
