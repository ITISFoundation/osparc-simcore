# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

"""
Keeps compatibility with old services/storage/client-sdk/python client (simcore_service_storage_sdk)

"""

from pathlib import Path

import aiohttp
import pytest
from aiohttp.test_utils import TestClient
from faker import Faker
from models_library.projects_nodes_io import LocationID, SimcoreS3FileID
from models_library.users import UserID
from simcore_service_storage.simcore_s3_dsm import SimcoreS3DataManager
from simcore_service_storage_sdk import ApiClient, Configuration, UsersApi

## from simcore_service_storage_sdk.rest import ApiException

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


#
# FIXTURES: produces values to be used as arguments in the simcore_service_storage_sdk API
#


@pytest.fixture
def user_id(user_id: UserID) -> str:
    """overrides tests/fixtures/data_models.py::user_id
    and adapts to simcore_service_storage_sdk API
    """
    return str(user_id)


@pytest.fixture
def file_id(simcore_file_id: SimcoreS3FileID) -> str:
    """overrides tests/conftest.py::simcore_file_id
    and adapts to simcore_service_storage_sdk API
    """
    return str(simcore_file_id)


@pytest.fixture
def location_id() -> LocationID:
    return SimcoreS3DataManager.get_location_id()


@pytest.fixture
def location_name() -> str:
    return SimcoreS3DataManager.get_location_name()


async def test_storage_client_used_in_simcore_sdk_0_3_2(
    client: TestClient,
    file_id: str,
    user_id: str,
    location_id: int,
    location_name: str,
    tmp_path: Path,
    faker: Faker,
):
    """
    This test has calls to 'simcore_service_storage_sdk' used
    in simcore_sdk.node_ports.filemanage (version 0.3.2)


    Specifically:
        simcore-sdk @ git+https://github.com/ITISFoundation/osparc-simcore.git@cfdf4f86d844ebb362f4f39e9c6571d561b72897#subdirectory=packages/simcore-sdk


    SEE https://github.com/ITISFoundation/osparc-simcore/blob/cfdf4f86d844ebb362f4f39e9c6571d561b72897/packages/simcore-sdk/src/simcore_sdk/node_ports/filemanager.py

    """

    assert client.app
    assert client.server
    # --------
    cfg = Configuration()
    cfg.host = f"http://{client.host}:{client.port}/v0"
    cfg.debug = True

    assert cfg.host == f'{client.make_url("/v0")}'
    print(f"{cfg=}")
    print(f"{cfg.to_debug_report()=}")

    # --------
    api_client = ApiClient(cfg)
    print(f"{api_client=}")
    print(f"{api_client.default_headers=}")

    # --------
    try:
        api = UsersApi(api_client)
        print(f"{api=}")

        (
            response_payload,
            status_code,
            response_headers,
        ) = await api.get_storage_locations_with_http_info(user_id)
        print(f"{response_payload=}")
        print(f"{status_code=}")
        print(f"{response_headers=}")

        assert status_code == 200

        # _get_upload_link
        # https://github.com/ITISFoundation/osparc-simcore/blob/cfdf4f86d844ebb362f4f39e9c6571d561b72897/packages/simcore-sdk/src/simcore_sdk/node_ports/filemanager.py#L132
        resp_model = await api.upload_file(
            location_id=location_id,
            user_id=user_id,
            file_id=file_id,
            _request_timeout=1000,
        )
        assert resp_model.error is None
        assert resp_model.data.link is not None

        # dumps file & upload
        file = tmp_path / Path(file_id).name
        file.write_text(faker.text())

        async with aiohttp.ClientSession() as session:
            with file.open("rb") as fh:
                async with session.put(resp_model.data.link, data=fh) as resp_model:
                    print(resp_model.status)
                    print(await resp_model.text())

        # entry_exists
        # https://github.com/ITISFoundation/osparc-simcore/blob/cfdf4f86d844ebb362f4f39e9c6571d561b72897/packages/simcore-sdk/src/simcore_sdk/node_ports/filemanager.py#L322
        #
        # NOTE: jupyter-smash 2.5.9 was failing to download because
        #   this call was not returning any 'object_name'
        #   A bug in the response of this call was preventing downloading data
        #   with the new storage API
        #
        resp_model = await api.get_file_metadata(file_id, location_id, user_id)
        print(type(resp_model), ":\n", resp_model)
        assert resp_model.data.object_name is not None
        assert resp_model.error is None

        # _get_location_id_from_location_name
        # https://github.com/ITISFoundation/osparc-simcore/blob/cfdf4f86d844ebb362f4f39e9c6571d561b72897/packages/simcore-sdk/src/simcore_sdk/node_ports/filemanager.py#L89
        resp_model = await api.get_storage_locations(user_id=user_id)
        print(f"{resp_model=}")
        for location in resp_model.data:
            assert location["name"] == location_name
            assert location["id"]

        # _get_download_link
        # https://github.com/ITISFoundation/osparc-simcore/blob/cfdf4f86d844ebb362f4f39e9c6571d561b72897/packages/simcore-sdk/src/simcore_sdk/node_ports/filemanager.py#L123
        resp_model = await api.download_file(
            location_id=location_id,
            user_id=user_id,
            file_id=file_id,
            _request_timeout=1000,
        )
        print(f"{resp_model=}")
        assert resp_model.error is None

    finally:
        del api_client
