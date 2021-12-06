# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict
from urllib.parse import quote

import pytest
import simcore_service_storage._meta
from aiohttp import web
from aiohttp.test_utils import TestClient
from simcore_service_storage.access_layer import AccessRights
from simcore_service_storage.app_handlers import HealthCheck
from simcore_service_storage.constants import APP_CONFIG_KEY, SIMCORE_S3_ID
from simcore_service_storage.db import setup_db
from simcore_service_storage.dsm import APP_DSM_KEY, DataStorageManager, setup_dsm
from simcore_service_storage.models import FileMetaData
from simcore_service_storage.rest import setup_rest
from simcore_service_storage.s3 import setup_s3
from simcore_service_storage.settings import Settings
from tests.helpers.utils_assert import assert_status
from tests.helpers.utils_project import clone_project_data
from tests.utils import BUCKET_NAME, USER_ID, has_datcore_tokens

current_dir = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent


def parse_db(dsm_mockup_db):
    id_name_map = {}
    id_file_count = {}
    for d in dsm_mockup_db.keys():
        md = dsm_mockup_db[d]
        if not md.user_id in id_name_map:
            id_name_map[md.user_id] = md.user_name
            id_file_count[md.user_id] = 1
        else:
            id_file_count[md.user_id] = id_file_count[md.user_id] + 1

    return id_file_count, id_name_map


@pytest.fixture
def client(
    loop,
    aiohttp_unused_port,
    aiohttp_client: TestClient,
    postgres_service,
    postgres_service_url,
    minio_service,
    osparc_api_specs_dir,
    monkeypatch,
):
    app = web.Application()

    # FIXME: postgres_service fixture environs different from project_env_devel_environment. Do it after https://github.com/ITISFoundation/osparc-simcore/pull/2276 resolved
    pg_config = postgres_service.copy()
    pg_config.pop("database")

    for key, value in pg_config.items():
        monkeypatch.setenv(f"POSTGRES_{key.upper()}", f"{value}")

    for key, value in minio_service.items():
        monkeypatch.setenv(f"S3_{key.upper()}", f"{value}")

    monkeypatch.setenv("STORAGE_PORT", str(aiohttp_unused_port()))
    monkeypatch.setenv("STORAGE_LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("STORAGE_TESTING", "1")

    monkeypatch.setenv("SC_BOOT_MODE", "local-development")

    settings = Settings.create_from_envs()
    print(settings.json(indent=2))

    app[APP_CONFIG_KEY] = settings

    setup_db(app)
    setup_rest(app)
    setup_dsm(app)
    setup_s3(app)

    cli = loop.run_until_complete(
        aiohttp_client(
            app, server_kwargs={"port": settings.STORAGE_PORT, "host": "localhost"}
        )
    )
    return cli


async def test_health_check(client):
    resp = await client.get("/v0/")
    text = await resp.text()

    assert resp.status == 200, text

    payload = await resp.json()
    data, error = tuple(payload.get(k) for k in ("data", "error"))

    assert data
    assert not error

    app_health = HealthCheck.parse_obj(data)
    assert app_health.name == simcore_service_storage._meta.app_name
    assert app_health.version == simcore_service_storage._meta.api_version


async def test_locations(client):
    user_id = USER_ID

    resp = await client.get("/v0/locations?user_id={}".format(user_id))

    payload = await resp.json()
    assert resp.status == 200, str(payload)

    data, error = tuple(payload.get(k) for k in ("data", "error"))

    _locs = 2 if has_datcore_tokens() else 1
    assert len(data) == _locs
    assert not error


async def test_s3_files_metadata(client, dsm_mockup_db):
    id_file_count, _id_name_map = parse_db(dsm_mockup_db)

    # list files for every user
    for _id in id_file_count:
        resp = await client.get("/v0/locations/0/files/metadata?user_id={}".format(_id))
        payload = await resp.json()
        assert resp.status == 200, str(payload)

        data, error = tuple(payload.get(k) for k in ("data", "error"))
        assert not error
        assert len(data) == id_file_count[_id]

    # list files fileterd by uuid
    for d in dsm_mockup_db.keys():
        fmd = dsm_mockup_db[d]
        uuid_filter = os.path.join(fmd.project_id, fmd.node_id)
        resp = await client.get(
            "/v0/locations/0/files/metadata?user_id={}&uuid_filter={}".format(
                fmd.user_id, quote(uuid_filter, safe="")
            )
        )
        payload = await resp.json()
        assert resp.status == 200, str(payload)

        data, error = tuple(payload.get(k) for k in ("data", "error"))
        assert not error
        for d in data:
            assert os.path.join(d["project_id"], d["node_id"]) == uuid_filter


async def test_s3_file_metadata(client, dsm_mockup_db):
    # go through all files and get them
    for d in dsm_mockup_db.keys():
        fmd = dsm_mockup_db[d]
        resp = await client.get(
            "/v0/locations/0/files/{}/metadata?user_id={}".format(
                quote(fmd.file_uuid, safe=""), fmd.user_id
            )
        )
        payload = await resp.json()
        assert resp.status == 200, str(payload)

        data, error = tuple(payload.get(k) for k in ("data", "error"))
        assert not error
        assert data


async def test_download_link(client, dsm_mockup_db):
    for d in dsm_mockup_db.keys():
        fmd = dsm_mockup_db[d]
        resp = await client.get(
            "/v0/locations/0/files/{}?user_id={}".format(
                quote(fmd.file_uuid, safe=""), fmd.user_id
            )
        )
        payload = await resp.json()
        assert resp.status == 200, str(payload)

        data, error = tuple(payload.get(k) for k in ("data", "error"))
        assert not error
        assert data


async def test_upload_link(client, dsm_mockup_db):
    for d in dsm_mockup_db.keys():
        fmd = dsm_mockup_db[d]
        resp = await client.put(
            "/v0/locations/0/files/{}?user_id={}".format(
                quote(fmd.file_uuid, safe=""), fmd.user_id
            )
        )
        payload = await resp.json()
        assert resp.status == 200, str(payload)

        data, error = tuple(payload.get(k) for k in ("data", "error"))
        assert not error
        assert data


@pytest.mark.skipif(not has_datcore_tokens(), reason="no datcore tokens")
async def test_copy(client, dsm_mockup_db, datcore_structured_testbucket):

    # copy N files
    N = 2
    counter = 0
    for d in dsm_mockup_db.keys():
        fmd = dsm_mockup_db[d]
        source_uuid = fmd.file_uuid
        datcore_id = datcore_structured_testbucket["coll1_id"]
        resp = await client.put(
            "/v0/locations/1/files/{}?user_id={}&extra_location={}&extra_source={}".format(
                quote(datcore_id, safe=""),
                fmd.user_id,
                SIMCORE_S3_ID,
                quote(source_uuid, safe=""),
            )
        )
        payload = await resp.json()
        assert resp.status == 200, str(payload)

        data, error = tuple(payload.get(k) for k in ("data", "error"))
        assert not error
        assert data

        counter = counter + 1
        if counter == N:
            break

    # list files for every user
    user_id = USER_ID
    resp = await client.get(
        "/v0/locations/1/files/metadata?user_id={}&uuid_filter={}".format(
            user_id, BUCKET_NAME
        )
    )
    payload = await resp.json()
    assert resp.status == 200, str(payload)

    data, error = tuple(payload.get(k) for k in ("data", "error"))
    assert not error
    assert len(data) > N


async def test_delete_file(client, dsm_mockup_db):
    id_file_count, _id_name_map = parse_db(dsm_mockup_db)

    for d in dsm_mockup_db.keys():
        fmd = dsm_mockup_db[d]
        resp = await client.delete(
            "/v0/locations/0/files/{}?user_id={}".format(
                quote(fmd.file_uuid, safe=""), fmd.user_id
            )
        )
        payload = await resp.json()
        assert resp.status == 200, str(payload)

        data, error = tuple(payload.get(k) for k in ("data", "error"))
        assert not error
        assert not data

    for _id in id_file_count:
        resp = await client.get("/v0/locations/0/files/metadata?user_id={}".format(_id))
        payload = await resp.json()
        assert resp.status == 200, str(payload)

        data, error = tuple(payload.get(k) for k in ("data", "error"))
        assert not error
        assert len(data) == 0


async def test_action_check(client):
    QUERY = "mguidon"
    ACTION = "echo"
    FAKE = {"path_value": "one", "query_value": "two", "body_value": {"a": 33, "b": 45}}

    resp = await client.post(f"/v0/check/{ACTION}?data={QUERY}", json=FAKE)
    payload = await resp.json()
    data, error = tuple(payload.get(k) for k in ("data", "error"))

    assert resp.status == 200, str(payload)
    assert data
    assert not error

    # TODO: validate response against specs

    assert data["path_value"] == ACTION
    assert data["query_value"] == QUERY


def get_project_with_data() -> Dict[str, Any]:
    projects = []
    with open(current_dir / "../data/projects_with_data.json") as fp:
        projects = json.load(fp)

    # TODO: add schema validation
    return projects


@pytest.fixture
def mock_datcore_download(mocker, client):
    # Use to mock downloading from DATCore
    async def _fake_download_to_file_or_raise(session, url, dest_path):
        print(f"Faking download:  {url} -> {dest_path}")
        Path(dest_path).write_text("FAKE: test_create_and_delete_folders_from_project")

    mocker.patch(
        "simcore_service_storage.dsm.download_to_file_or_raise",
        side_effect=_fake_download_to_file_or_raise,
    )

    dsm = client.app[APP_DSM_KEY]
    assert dsm
    assert isinstance(dsm, DataStorageManager)

    async def mock_download_link_datcore(*args, **kwargs):
        return ["https://httpbin.org/image", "foo.txt"]

    mocker.patch.object(dsm, "download_link_datcore", mock_download_link_datcore)


@pytest.fixture
def mock_get_project_access_rights(mocker) -> None:
    # NOTE: this avoid having to inject project in database
    for module in ("dsm", "access_layer"):
        mock = mocker.patch(
            f"simcore_service_storage.{module}.get_project_access_rights"
        )
        mock.return_value.set_result(AccessRights.all())


async def _create_and_delete_folders_from_project(
    project: Dict[str, Any], client: TestClient
):
    destination_project, nodes_map = clone_project_data(project)

    # CREATING
    url = (
        client.app.router["copy_folders_from_project"].url_for().with_query(user_id="1")
    )
    resp = await client.post(
        url,
        json={
            "source": project,
            "destination": destination_project,
            "nodes_map": nodes_map,
        },
    )

    data, _error = await assert_status(resp, expected_cls=web.HTTPCreated)

    # data should be equal to the destination project, and all store entries should point to simcore.s3
    for key in data:
        if key != "workbench":
            assert data[key] == destination_project[key]
        else:
            for _node_id, node in data[key].items():
                if "outputs" in node:
                    for _o_id, o in node["outputs"].items():
                        if "store" in o:
                            assert o["store"] == SIMCORE_S3_ID

    # DELETING
    project_id = data["uuid"]
    url = (
        client.app.router["delete_folders_of_project"]
        .url_for(folder_id=project_id)
        .with_query(user_id="1")
    )
    resp = await client.delete(url)

    await assert_status(resp, expected_cls=web.HTTPNoContent)


@pytest.mark.parametrize(
    "project_name,project", [(prj["name"], prj) for prj in get_project_with_data()]
)
async def test_create_and_delete_folders_from_project(
    client: TestClient,
    dsm_mockup_db: Dict[str, FileMetaData],
    project_name: str,
    project: Dict[str, Any],
    mock_get_project_access_rights,
    mock_datcore_download,
):
    source_project = project
    await _create_and_delete_folders_from_project(source_project, client)


@pytest.mark.parametrize(
    "project_name,project", [(prj["name"], prj) for prj in get_project_with_data()]
)
async def test_create_and_delete_folders_from_project_burst(
    client,
    dsm_mockup_db,
    project_name,
    project,
    mock_get_project_access_rights,
    mock_datcore_download,
):
    source_project = project
    import asyncio

    await asyncio.gather(
        *[
            _create_and_delete_folders_from_project(source_project, client)
            for _ in range(100)
        ]
    )


async def test_s3_datasets_metadata(client):
    url = (
        client.app.router["get_datasets_metadata"]
        .url_for(location_id=str(SIMCORE_S3_ID))
        .with_query(user_id="21")
    )
    resp = await client.get(url)
    payload = await resp.json()
    assert resp.status == 200, str(payload)
    data, error = tuple(payload.get(k) for k in ("data", "error"))
    assert not error


async def test_s3_files_datasets_metadata(client):
    url = (
        client.app.router["get_files_metadata_dataset"]
        .url_for(location_id=str(SIMCORE_S3_ID), dataset_id="aa")
        .with_query(user_id="21")
    )
    resp = await client.get(url)
    payload = await resp.json()
    assert resp.status == 200, str(payload)
    data, error = tuple(payload.get(k) for k in ("data", "error"))
    assert not error
