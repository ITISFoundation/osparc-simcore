# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

"""
Tests compatibility of old services/storage/client-sdk/python client ('simcore_service_storage_sdk')
against current storage OAS


NOTE: this test coverage is intentionally limited to the functions of 'simcore_service_storage_sdk'
used in simcore_sdk since legacy services are planned to be deprecated.
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

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


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


async def test_storage_client_used_in_simcore_sdk_0_3_2(  # noqa: PLR0915
    client: TestClient,
    file_id: str,
    user_id: str,
    location_id: int,
    location_name: str,
    tmp_path: Path,
    faker: Faker,
):
    """
    This test reproduces the failure described in https://github.com/ITISFoundation/osparc-simcore/pull/3198
    where a legacy service could not download data from s3.

    Here we test the calls from 'simcore_service_storage_sdk' used in simcore_sdk.node_ports.filemanage (v0.3.2)
    SEE https://github.com/ITISFoundation/osparc-simcore/blob/cfdf4f86d844ebb362f4f39e9c6571d561b72897/packages/simcore-sdk/src/simcore_sdk/node_ports/filemanager.py

    NOTICE that 'simcore_service_storage_sdk' was automatically built using OAS v0.1.0 despite the fact that at that time
    the OAS had already change!!!
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
        uploaded_content = faker.text()
        file.write_text(uploaded_content)

        async with aiohttp.ClientSession() as session:
            with file.open("rb") as fh:
                async with session.put(resp_model.data.link, data=fh) as r:
                    assert r.status == 200, await r.text()
                    print(await r.text())

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
            assert location["id"] == location_id

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

        async with aiohttp.ClientSession() as session:
            async with session.get(resp_model.data.link) as r:
                print(r.status)
                downloaded_content = await r.text()
                assert r.status == 200, downloaded_content
                assert uploaded_content == downloaded_content

    finally:
        del api_client
