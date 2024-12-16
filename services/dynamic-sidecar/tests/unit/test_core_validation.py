# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument

from inspect import signature
from pathlib import Path

import pytest
from fastapi import FastAPI
from models_library.projects_nodes_io import NodeID
from models_library.services_types import ServiceRunID
from pytest_mock import MockerFixture
from servicelib.docker_constants import DEFAULT_USER_SERVICES_NETWORK_NAME
from simcore_service_dynamic_sidecar.core.validation import (
    _connect_user_services,
    parse_compose_spec,
    validate_compose_spec,
)
from simcore_service_dynamic_sidecar.modules.mounted_fs import MountedVolumes


@pytest.fixture
def incoming_iseg_compose_file_content() -> str:
    return """
networks:
  dy-sidecar_6f54ecb4-cac2-424a-8b72-ee9366026ff8:
    driver: overlay
    name: dy-sidecar_6f54ecb4-cac2-424a-8b72-ee9366026ff8
    external: true
services:
  iseg-app:
    image: registry.osparc.org/simcore/services/dynamic/iseg-app:1.0.7
  iseg-web:
    image: registry.osparc.org/simcore/services/dynamic/iseg-web:1.0.7
    networks:
      dy-sidecar_6f54ecb4-cac2-424a-8b72-ee9366026ff8:
version: \'3.7\'
    """


@pytest.fixture
def incoming_iseg_compose_file_content_missing_network() -> str:
    return """
networks:
services:
  iseg-app:
    image: registry.osparc.org/simcore/services/dynamic/iseg-app:1.0.7
  iseg-web:
    image: registry.osparc.org/simcore/services/dynamic/iseg-web:1.0.7
    networks:
      dy-sidecar_6f54ecb4-cac2-424a-8b72-ee9366026ff8:
version: \'3.7\'
    """


@pytest.fixture
def incoming_iseg_compose_file_content_missing_network_list() -> str:
    return """
networks:
services:
  iseg-app:
    image: registry.osparc.org/simcore/services/dynamic/iseg-app:1.0.7
  iseg-web:
    image: registry.osparc.org/simcore/services/dynamic/iseg-web:1.0.7
    networks:
      - dy-sidecar_6f54ecb4-cac2-424a-8b72-ee9366026ff8
version: \'3.7\'
    """


@pytest.fixture
def incoming_iseg_compose_file_content_no_networks() -> str:
    return """
services:
  iseg-app:
    image: registry.osparc.org/simcore/services/dynamic/iseg-app:1.0.7
  iseg-web:
    image: registry.osparc.org/simcore/services/dynamic/iseg-web:1.0.7
version: \'3.7\'
    """


@pytest.fixture(
    params=[
        "incoming_iseg_compose_file_content",
        "incoming_iseg_compose_file_content_missing_network",
        "incoming_iseg_compose_file_content_missing_network_list",
        "incoming_iseg_compose_file_content_no_networks",
    ]
)
def incoming_compose_file(
    request,
    incoming_iseg_compose_file_content: str,
    incoming_iseg_compose_file_content_missing_network: str,
    incoming_iseg_compose_file_content_missing_network_list: str,
    incoming_iseg_compose_file_content_no_networks: str,
) -> str:
    # check that fixture_name is present in this function's parameters
    fixture_name = request.param
    sig = signature(incoming_compose_file)
    assert fixture_name in sig.parameters, (
        f"Provided fixture name {fixture_name} was not found "
        f"as a parameter in the signature {sig}"
    )

    # returns the parameter by name from the ones declared in the signature
    result: str = locals()[fixture_name]
    return result


@pytest.mark.parametrize(
    "networks",
    [
        pytest.param(None, id="no_networks"),
        pytest.param({}, id="empty_dict"),
        pytest.param({"a_network": None}, id="existing_network"),
    ],
)
@pytest.mark.parametrize("allow_internet_access", [True, False])
def test_inject_backend_networking(
    networks: None | dict, incoming_compose_file: str, allow_internet_access: bool
):
    """
    NOTE: this goes with issue [https://github.com/ITISFoundation/osparc-simcore/issues/3261]
    """
    parsed_compose_spec = parse_compose_spec(incoming_compose_file)
    parsed_compose_spec["networks"] = networks
    _connect_user_services(
        parsed_compose_spec, allow_internet_access=allow_internet_access
    )
    assert DEFAULT_USER_SERVICES_NETWORK_NAME in parsed_compose_spec["networks"]
    assert (
        DEFAULT_USER_SERVICES_NETWORK_NAME
        in parsed_compose_spec["services"]["iseg-app"]["networks"]
    )
    assert (
        DEFAULT_USER_SERVICES_NETWORK_NAME
        in parsed_compose_spec["services"]["iseg-web"]["networks"]
    )


@pytest.fixture
def mock_get_volume_by_label(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_dynamic_sidecar.modules.mounted_fs.get_volume_by_label",
        autospec=True,
        return_value={"Mountpoint": "/fake/mount"},
    )


@pytest.fixture
def no_internet_spec(project_tests_dir: Path) -> str:
    no_intenret_file = project_tests_dir / "mocks" / "internet_blocked_spec.yaml"
    return no_intenret_file.read_text()


@pytest.fixture
def fake_mounted_volumes() -> MountedVolumes:
    return MountedVolumes(
        service_run_id=ServiceRunID.create_for_dynamic_sidecar(),
        node_id=NodeID("a019b83f-7cce-46bf-90cf-d02f7f0f089a"),
        inputs_path=Path("/"),
        outputs_path=Path("/"),
        user_preferences_path=None,
        state_paths=[],
        state_exclude=set(),
        compose_namespace="",
        dy_volumes=Path("/"),
    )


async def test_regression_validate_compose_spec(
    mock_get_volume_by_label: None,
    app: FastAPI,
    no_internet_spec: str,
    fake_mounted_volumes: MountedVolumes,
):
    await validate_compose_spec(
        app.state.settings, no_internet_spec, fake_mounted_volumes
    )
