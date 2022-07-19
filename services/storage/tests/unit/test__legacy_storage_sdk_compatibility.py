# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

"""
Keeps compatibility with old services/storage/client-sdk/python client (simcore_service_storage_sdk)

"""

import pytest
from aiohttp.test_utils import TestClient
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
def store_id() -> LocationID:
    return SimcoreS3DataManager.get_location_id()


@pytest.fixture
def store_name() -> str:
    return SimcoreS3DataManager.get_location_name()


async def test_storage_client_used_in_simcore_sdk_0_3_2(
    client: TestClient,
    file_id: str,
    user_id: str,
    store_id: int,
    store_name: str,
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
    cfg = Configuration()
    cfg.host = f"http://{client.host}:{client.port}/v0"
    cfg.debug = True

    assert cfg.host == f'{client.make_url("/v0")}'

    print(f"{cfg=}")
    print(f"{cfg.to_debug_report()=}")

    api_client = ApiClient(cfg)
    print(f"{api_client=}")
    print(f"{api_client.default_headers=}")

    try:
        api = UsersApi(api_client)
        print(f"{api=}")

        # entry_exists
        # https://github.com/ITISFoundation/osparc-simcore/blob/cfdf4f86d844ebb362f4f39e9c6571d561b72897/packages/simcore-sdk/src/simcore_sdk/node_ports/filemanager.py#L322
        # A bug in the response of this call was preventing downloading data with the new storage API
        resp = await api.get_file_metadata(file_id, store_id, user_id)
        print(f"{resp=}")
        assert resp.data.object_name is not None

        # _get_location_id_from_location_name
        # https://github.com/ITISFoundation/osparc-simcore/blob/cfdf4f86d844ebb362f4f39e9c6571d561b72897/packages/simcore-sdk/src/simcore_sdk/node_ports/filemanager.py#L89
        resp = await api.get_storage_locations(user_id=user_id)
        print(f"{resp=}")
        for location in resp.data:
            assert location["name"] == store_name
            assert location["id"]

        # _get_download_link
        # https://github.com/ITISFoundation/osparc-simcore/blob/cfdf4f86d844ebb362f4f39e9c6571d561b72897/packages/simcore-sdk/src/simcore_sdk/node_ports/filemanager.py#L123
        download_link = await api.download_file(
            location_id=store_id,
            user_id=user_id,
            file_id=file_id,
            _request_timeout=1000,
        )
        assert download_link

        # _get_upload_link
        # https://github.com/ITISFoundation/osparc-simcore/blob/cfdf4f86d844ebb362f4f39e9c6571d561b72897/packages/simcore-sdk/src/simcore_sdk/node_ports/filemanager.py#L132
        upload_link = await api.upload_file(
            location_id=store_id,
            user_id=user_id,
            file_id=file_id,
            _request_timeout=1000,
        )
        assert upload_link

    finally:
        del api_client
