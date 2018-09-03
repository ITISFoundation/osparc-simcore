import logging

from server.resources import (
    ConfigFile
)

_LOGGER = logging.getLogger(__name__)

def test_configfile(package_paths):

    assert package_paths.CONFIG_FOLDER.exists()

    config_names = ConfigFile.list_all()
    assert config_names

    config_paths = list(package_paths.CONFIG_FOLDER.glob("*.yaml"))
    assert len(config_paths) == len(config_names)

    for name in config_names:
        with ConfigFile(name) as fh:
            assert fh.read()
