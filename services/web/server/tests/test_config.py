import inspect
import pathlib
import logging
import os
import sys

import pytest

# under test
import server.settings
import server.cli as srv_cli



# TODO: pass dirs as fixture. See default pytest conf fixture!
CURRENT_DIR = pathlib.Path( sys.argv[0] if __name__ == "__main__" else __file__).parent
CONFIG_DIR = CURRENT_DIR.parent / "config"

_LOGGER = logging.getLogger(__name__)


def test_config_options_in_cli(capsys):
    with pytest.raises(SystemExit) as einfo:
        ap = srv_cli.add_options()
        assert ap is not None

        cmd = "--help"
        srv_cli.parse_options(cmd.split(), ap)

        captured = capsys.readouterror()
        assert "--config" in captured.out
        assert "--print-config" in captured.out
        assert "--print-config-vars" in captured.out

    assert einfo.value.code == 0


def test_validate_available_config_files():
    count = 0
    for configpath in CONFIG_DIR.glob("*.yaml"):
        # raises ConfigError if fails
        server.settings.read_and_validate(configpath)
        count +=1
    assert count!=0
