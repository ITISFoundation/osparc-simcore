import logging
import os
import unittest.mock as mock

import pytest

# under test
from server.settings.config import CONFIG_SCHEMA
import server.settings
import server.cli as srv_cli

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


def test_validate_available_config_files(package_paths):
    import trafaret_config.simple as _ts

    count = 0
    for config_path in package_paths.CONFIG_FOLDER.glob("*.yaml"):

        config_vars = _ts.read_and_get_vars(config_path, CONFIG_SCHEMA, vars=os.environ)

        mock_environ = {}
        for name in config_vars:
            fake_value = "1234" if "port" in name.lower() else "foo"
            mock_environ[name] = fake_value

        with mock.patch('os.environ', mock_environ):
            server.settings.read_and_validate(config_path)
            count +=1

        assert count!=0
