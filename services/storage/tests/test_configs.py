# pylint:disable=wildcard-import
# pylint:disable=unused-import
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import argparse
import re
import unittest.mock as mock

import pytest
import yaml

from simcore_service_storage.cli import create_environ, parse, setup_parser
from simcore_service_storage.resources import resources

THIS_SERVICE = "storage"
CONFIG_DIR = "data"


@pytest.fixture("session")
def env_devel_file(osparc_simcore_root_dir):
    env_devel_fpath = osparc_simcore_root_dir / ".env-devel"
    assert env_devel_fpath.exists()
    return env_devel_fpath


@pytest.fixture("session")
def services_docker_compose_file(osparc_simcore_root_dir):
    dcpath = osparc_simcore_root_dir / "services" / "docker-compose.yml"
    assert dcpath.exists()
    return dcpath


@pytest.fixture("session")
def devel_environ(env_devel_file):
    PATTERN_ENVIRON_EQUAL = re.compile(r"^(\w+)=(.*)$")
    env_devel = {}
    with env_devel_file.open() as f:
        for line in f:
            m = PATTERN_ENVIRON_EQUAL.match(line)
            if m:
                key, value = m.groups()
                env_devel[key] = str(value)
    return env_devel


variable_expansion_pattern = re.compile(r"\$\{*(\w+)+[:-]*(\w+)*\}")

@pytest.mark.parametrize(
    "sample,expected_match",
    [
        (r"${varname:-default}", ("varname", "default")),
        (r"${varname}", ("varname", None)),
        (r"33", None),
        (r"${VAR_name:-33}", ("VAR_name", "33")),
        (r"${varname-default}", ("varname", "default")), # this is not standard!
        (r"${varname:default}", ("varname", "default")), # this is not standard!
    ],
)
def test_variable_expansions(sample, expected_match):
    # TODO: extend variable expansions
    # https://en.wikibooks.org/wiki/Bourne_Shell_Scripting/Variable_Expansion
    match = variable_expansion_pattern.match(sample)
    if expected_match:
        assert match
        varname, default = match.groups()
        assert (varname, default) == expected_match
    else:
        assert not match


@pytest.fixture("session")
def container_environ(
    services_docker_compose_file, devel_environ, osparc_simcore_root_dir
):
    """ Creates a dict with the environment variables
        inside of a webserver container
    """
    dc = dict()
    with services_docker_compose_file.open() as f:
        dc = yaml.safe_load(f)

    container_environ = create_environ(skip_system_environ=True)
    container_environ.update(
        {"OSPARC_SIMCORE_REPO_ROOTDIR": str(osparc_simcore_root_dir)}
    )

    environ_items = dc["services"][THIS_SERVICE].get("environment", list())

    for item in environ_items:
        key, value = item.split("=")

        match = variable_expansion_pattern.match(value)
        if match:
            varname, default_value = match.groups()
            value = devel_environ.get(varname, default_value)
        container_environ[key] = value

    return container_environ


@pytest.mark.parametrize(
    "configfile",
    [str(n) for n in resources.listdir(CONFIG_DIR) if n.endswith(("yaml", "yml"))],
)
def test_config_files(configfile, container_environ, capsys):
    parser = setup_parser(argparse.ArgumentParser("test-parser"))

    with mock.patch("os.environ", container_environ):
        cmd = ["-c", configfile]
        try:
            config = parse(cmd, parser)

        except SystemExit as err:
            pytest.fail(capsys.readouterr().err)

        for key, value in config.items():
            assert value != "None", "Use instead Null in {} for {}".format(
                configfile, key
            )
