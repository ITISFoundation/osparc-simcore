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

import logging
import sys
from copy import deepcopy
from pathlib import Path
from pprint import pprint
from typing import Dict, List
from unittest import mock

import pytest
import trafaret_config
import yaml
from pytest_mock import MockerFixture
from pytest_simcore.helpers import FIXTURE_CONFIG_CORE_SERVICES_SELECTION
from pytest_simcore.helpers.utils_docker import get_service_published_port
from pytest_simcore.helpers.utils_login import NewUser
from simcore_service_webserver.application_config import app_schema
from simcore_service_webserver.cli import create_environ
from simcore_service_webserver.groups_api import (
    add_user_in_group,
    create_user_group,
    delete_user_group,
    list_user_groups,
)
from simcore_service_webserver.resources import resources as app_resources

CURRENT_DIR = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

# NOTE:

log = logging.getLogger(__name__)


@pytest.fixture(scope="module")
def webserver_environ(
    request, docker_stack: Dict, simcore_docker_compose: Dict
) -> Dict[str, str]:
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
    services_with_published_ports = [
        name
        for name in core_services
        if "ports" in simcore_docker_compose["services"][name]
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

    pprint(environ)  # NOTE: displayed only if error
    return environ


@pytest.fixture(scope="module")
def _webserver_dev_config(
    webserver_environ: Dict, docker_stack: Dict, temp_folder: Path
) -> Dict:
    """
    Swarm with integration stack already started

    Configuration for a webserver provided it runs in host

    NOTE: Prefer using 'app_config' below instead of this as a function-scoped fixture
    """
    config_file_path = temp_folder / "webserver_dev_config.yaml"

    # recreate config-file
    with app_resources.stream("config/server-docker-dev.yaml") as f:
        cfg = yaml.safe_load(f)
        # test webserver works in host
        cfg["main"]["host"] = "127.0.0.1"

    with config_file_path.open("wt") as f:
        yaml.dump(cfg, f, default_flow_style=False)

    # Emulates cli
    config_environ = {}
    config_environ.update(webserver_environ)
    config_environ.update(
        create_environ(skip_host_environ=True)
    )  # TODO: can be done monkeypathcing os.environ and calling create_environ as well

    # validates
    cfg_dict = trafaret_config.read_and_validate(
        config_file_path, app_schema, vars=config_environ
    )

    # WARNING: changes to this fixture during testing propagates to other tests. Use cfg = deepcopy(cfg_dict)
    # FIXME:  freeze read/only json obj
    yield cfg_dict

    # clean up
    # to debug configuration uncomment next line
    config_file_path.unlink()

    return cfg_dict


@pytest.fixture(scope="function")
def app_config(_webserver_dev_config: Dict, aiohttp_unused_port) -> Dict:
    """
    Swarm with integration stack already started
    This fixture can be safely modified during test since it is renovated on every call
    """
    cfg = deepcopy(_webserver_dev_config)
    cfg["main"]["port"] = aiohttp_unused_port()

    return cfg


@pytest.fixture
def mock_orphaned_services(mocker: MockerFixture) -> mock.Mock:
    remove_orphaned_services = mocker.patch(
        "simcore_service_webserver.resource_manager.garbage_collector.remove_orphaned_services",
        return_value="",
    )
    return remove_orphaned_services


@pytest.fixture
async def primary_group(client, logged_user) -> Dict[str, str]:
    primary_group, _, _ = await list_user_groups(client.app, logged_user["id"])
    return primary_group


@pytest.fixture
async def standard_groups(client, logged_user: Dict) -> List[Dict[str, str]]:
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
            sparc_group["gid"],
            new_user_id=logged_user["id"],
        )
        await add_user_in_group(
            client.app,
            admin_user["id"],
            team_black_group["gid"],
            new_user_email=logged_user["email"],
        )

        _, standard_groups, _ = await list_user_groups(client.app, logged_user["id"])
        yield standard_groups
        # clean groups
        await delete_user_group(client.app, admin_user["id"], sparc_group["gid"])
        await delete_user_group(client.app, admin_user["id"], team_black_group["gid"])


@pytest.fixture
async def all_group(client, logged_user) -> Dict[str, str]:
    _, _, all_group = await list_user_groups(client.app, logged_user["id"])
    return all_group
