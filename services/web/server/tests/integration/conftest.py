""" Configuration for integration testing

    During integration testing,
        - the app under test (i.e. the webserver) will be installed and started in the host
        - every test module (i.e. integration/**/test_*.py) deploys a stack in a swarm fixture with a seleciton of core and op-services
        - the selection of core/op services are listed in the 'core_services' and 'ops_serices' variables in each test module

  NOTE: services/web/server/tests/conftest.py is pre-loaded

"""
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
import logging
import sys
from collections.abc import AsyncIterable
from copy import deepcopy
from pathlib import Path
from string import Template
from unittest import mock

import pytest
import yaml
from pytest_mock import MockerFixture
from pytest_simcore.helpers import FIXTURE_CONFIG_CORE_SERVICES_SELECTION
from pytest_simcore.helpers.utils_dict import ConfigDict
from pytest_simcore.helpers.utils_docker import get_service_published_port
from pytest_simcore.helpers.utils_login import NewUser, UserInfoDict
from simcore_service_webserver.groups.api import (
    add_user_in_group,
    create_user_group,
    delete_user_group,
    list_user_groups,
)

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

# NOTE:

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def webserver_environ(
    request, docker_stack: dict, simcore_docker_compose: dict
) -> dict[str, str]:
    """
    Started already swarm with integration stack (via dependency with 'docker_stack')

    Environment variable expected for the web-server application in
    an test-integration context, i.e. web-server runs in host and the
    remaining services (defined in variable 'core_services') are deployed
    in containers
    """
    assert "webserver" not in docker_stack["services"]

    docker_compose_environ = simcore_docker_compose["services"]["webserver"].get(
        "environment", {}
    )

    environ = {}
    environ.update(docker_compose_environ)

    # get the list of core services the test module wants
    core_services = getattr(request.module, FIXTURE_CONFIG_CORE_SERVICES_SELECTION, [])

    # OVERRIDES:
    #   One of the biggest differences with respect to the real system
    #   is that the webserver application is replaced by a light-weight
    #   version tha loads only the subsystems under test. For that reason,
    #   the test webserver is built-up in webserver_service fixture that runs
    #   on the host.
    EXCLUDED_SERVICES = ["dask-scheduler"]
    services_with_published_ports = [
        name
        for name in core_services
        if "ports" in simcore_docker_compose["services"][name]
        and name not in EXCLUDED_SERVICES
    ]
    for name in services_with_published_ports:
        host_key = f"{name.upper().replace('-', '_')}_HOST"
        port_key = f"{name.upper().replace('-', '_')}_PORT"

        # published port is sometimes dynamically defined by the swarm
        assert (
            host_key in environ
        ), "Variables names expected to be prefix with service names in docker-compose"
        assert port_key in environ

        # to swarm boundary since webserver is installed in the host and therefore outside the swarm's network
        published_port = get_service_published_port(name, int(environ[port_key]))
        environ[host_key] = "127.0.0.1"
        environ[port_key] = published_port

    print("webserver_environ:", json.dumps(environ, indent=1, sort_keys=True))
    return environ


@pytest.fixture(scope="session")
def default_app_config_integration_file(tests_data_dir: Path) -> Path:
    cfg_path = tests_data_dir / "default_app_config-integration.yaml"
    assert cfg_path.exists()
    return cfg_path


@pytest.fixture(scope="module")
def _default_app_config_for_integration_tests(
    default_app_config_integration_file: Path,
    webserver_environ: dict,
    osparc_simcore_root_dir: Path,
) -> ConfigDict:
    """
    Swarm with integration stack already started

    Configuration for a webserver provided it runs in host

    NOTE: DO NOT USE directly, use instead function-scoped fixture 'app_config'
    """
    test_environ = {}
    test_environ.update(webserver_environ)

    # DEFAULTS if not defined in environ
    # NOTE: unfortunately, trafaret does not allow defining default directly in the config.yaml
    # as docker-compose does: i.e. x = ${VARIABLE:default}.
    #
    # Instead, the variables have to be defined here ------------
    test_environ["SMTP_USERNAME"] = "None"
    test_environ["SMTP_PASSWORD"] = "None"
    test_environ["SMTP_PROTOCOL"] = "UNENCRYPTED"
    test_environ["WEBSERVER_LOGLEVEL"] = "WARNING"
    test_environ["OSPARC_SIMCORE_REPO_ROOTDIR"] = f"{osparc_simcore_root_dir}"

    # NOTE: previously in .env but removed from that file env since the webserver
    # can be configured as GC service as well. In integration tests, we are
    # for the moment using web-server as an all-in-one service.
    # TODO: create integration tests using different configs
    # SEE https://github.com/ITISFoundation/osparc-simcore/issues/2896
    test_environ[
        "WEBSERVER_GARBAGE_COLLECTOR"
    ] = "{}"  # by default it is disabled. This enables it with default or env variables
    test_environ["GARBAGE_COLLECTOR_INTERVAL_S"] = "30"

    # recreate config-file
    config_template = Template(default_app_config_integration_file.read_text())
    config_text = config_template.substitute(**test_environ)
    cfg: ConfigDict = yaml.safe_load(config_text)

    # NOTE:  test webserver works in host
    cfg["main"]["host"] = "127.0.0.1"

    print(
        "_default_app_config_for_integration_tests:",
        json.dumps(cfg, indent=1, sort_keys=True),
    )
    return cfg


@pytest.fixture()
def app_config(
    _default_app_config_for_integration_tests: ConfigDict, unused_tcp_port_factory
) -> ConfigDict:
    """
    Swarm with integration stack already started
    This fixture can be safely modified during test since it is renovated on every call
    """
    cfg = deepcopy(_default_app_config_for_integration_tests)
    cfg["main"]["port"] = unused_tcp_port_factory()

    return cfg


@pytest.fixture
def mock_orphaned_services(mocker: MockerFixture) -> mock.Mock:
    return mocker.patch(
        "simcore_service_webserver.garbage_collector._core.remove_orphaned_services",
        return_value="",
    )


@pytest.fixture
async def primary_group(client, logged_user: UserInfoDict) -> dict[str, str]:
    primary_group, _, _ = await list_user_groups(client.app, logged_user["id"])
    return primary_group


@pytest.fixture
async def standard_groups(
    client, logged_user: UserInfoDict
) -> AsyncIterable[list[dict[str, str]]]:
    # create a separate admin account to create some standard groups for the logged user
    sparc_group = {
        "gid": "5",  # this will be replaced
        "label": "SPARC",
        "description": "Stimulating Peripheral Activity to Relieve Conditions",
        "thumbnail": "https://commonfund.nih.gov/sites/default/files/sparc-image-homepage500px.png",
    }
    team_black_group = {
        "gid": "5",  # this will be replaced
        "label": "team Black",
        "description": "THE incredible black team",
        "thumbnail": None,
    }
    async with NewUser(
        {"name": f"{logged_user['name']}_admin", "role": "USER"}, client.app
    ) as admin_user:
        sparc_group = await create_user_group(client.app, admin_user["id"], sparc_group)
        team_black_group = await create_user_group(
            client.app, admin_user["id"], team_black_group
        )
        await add_user_in_group(
            client.app,
            admin_user["id"],
            int(sparc_group["gid"]),
            new_user_id=logged_user["id"],
        )
        await add_user_in_group(
            client.app,
            admin_user["id"],
            int(team_black_group["gid"]),
            new_user_email=logged_user["email"],
        )

        _, standard_groups, _ = await list_user_groups(client.app, logged_user["id"])

        yield standard_groups

        # clean groups
        await delete_user_group(client.app, admin_user["id"], int(sparc_group["gid"]))
        await delete_user_group(
            client.app, admin_user["id"], int(team_black_group["gid"])
        )


@pytest.fixture
async def all_group(client, logged_user) -> dict[str, str]:
    _, _, all_group = await list_user_groups(client.app, logged_user["id"])
    return all_group


@pytest.fixture(scope="session")
def osparc_product_name() -> str:
    return "osparc"
