# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import logging
import random
from collections.abc import Iterator
from threading import Thread
from typing import Any
from urllib.parse import quote

import pytest
import uvicorn
from aiohttp.test_utils import TestClient
from faker import Faker
from fastapi import APIRouter, FastAPI, Request
from models_library.api_schemas_storage import (
    DatasetMetaDataGet,
    FileLocation,
    FileMetaDataGet,
    FileMetaDataGetv010,
)
from models_library.generics import Envelope
from models_library.projects import ProjectID
from models_library.users import UserID
from pytest_simcore.helpers.assert_checks import assert_status
from pytest_simcore.helpers.logging_tools import log_context
from servicelib.aiohttp import status
from servicelib.utils import unused_port
from simcore_postgres_database.models.users import UserRole
from yarl import URL

API_VERSION = "v0"


@pytest.fixture(scope="session")
def storage_vtag() -> str:
    return "v9"


@pytest.fixture(scope="module")
def fake_storage_app(storage_vtag: str) -> FastAPI:
    app = FastAPI(debug=True)
    router = APIRouter(
        prefix=f"/{storage_vtag}",
    )

    @router.get("/")
    async def _root(request: Request):
        return {"message": "Hello World"}

    @router.get(
        "/locations",
        status_code=status.HTTP_200_OK,
        response_model=Envelope[list[FileLocation]],
    )
    async def _list_storage_locations(user_id: UserID, request: Request):
        assert "json_schema_extra" in FileLocation.model_config
        assert isinstance(FileLocation.model_config["json_schema_extra"], dict)
        assert isinstance(
            FileLocation.model_config["json_schema_extra"]["examples"], list
        )

        return Envelope[list[FileLocation]](
            data=[
                FileLocation.model_validate(e)
                for e in FileLocation.model_config["json_schema_extra"]["examples"]
            ]
        )

    @router.get(
        "/locations/{location_id}/files/metadata",
        response_model=Envelope[list[FileMetaDataGet]],
    )
    async def _list_files_metadata(
        user_id: UserID,
        request: Request,
        uuid_filter: str = "",
        project_id: ProjectID | None = None,
        expand_dirs: bool = True,
    ):
        assert "json_schema_extra" in FileMetaDataGet.model_config
        assert isinstance(FileMetaDataGet.model_config["json_schema_extra"], dict)
        assert isinstance(
            FileMetaDataGet.model_config["json_schema_extra"]["examples"], list
        )
        if uuid_filter:
            return Envelope[list[FileMetaDataGet]](
                data=random.sample(
                    [
                        FileMetaDataGet.model_validate(e)
                        for e in FileMetaDataGet.model_config["json_schema_extra"][
                            "examples"
                        ]
                    ],
                    2,
                )
            )
        return Envelope[list[FileMetaDataGet]](
            data=[
                FileMetaDataGet.model_validate(e)
                for e in FileMetaDataGet.model_config["json_schema_extra"]["examples"]
            ]
        )

    @router.get(
        "/locations/{location_id}/files/{file_id:path}/metadata",
        response_model=Envelope[FileMetaDataGet]
        | Envelope[FileMetaDataGetv010]
        | Envelope[dict],
    )
    async def _get_file_metadata(user_id: UserID, request: Request):
        assert "json_schema_extra" in FileMetaDataGet.model_config
        assert isinstance(FileMetaDataGet.model_config["json_schema_extra"], dict)
        assert isinstance(
            FileMetaDataGet.model_config["json_schema_extra"]["examples"], list
        )
        return Envelope[FileMetaDataGet](
            data=random.choice(  # noqa: S311
                [
                    FileMetaDataGet.model_validate(e)
                    for e in FileMetaDataGet.model_config["json_schema_extra"][
                        "examples"
                    ]
                ]
            )
        )

    @router.get(
        "/locations/{location_id}/datasets",
        response_model=Envelope[list[DatasetMetaDataGet]],
    )
    async def _list_datasets_metadata(user_id: UserID, request: Request):
        assert "json_schema_extra" in DatasetMetaDataGet.model_config
        assert isinstance(DatasetMetaDataGet.model_config["json_schema_extra"], dict)
        assert isinstance(
            DatasetMetaDataGet.model_config["json_schema_extra"]["examples"], list
        )
        return Envelope[list[DatasetMetaDataGet]](
            data=[
                DatasetMetaDataGet.model_validate(e)
                for e in DatasetMetaDataGet.model_config["json_schema_extra"][
                    "examples"
                ]
            ]
        )

    @router.get(
        "/locations/{location_id}/datasets/{dataset_id}/metadata",
        response_model=Envelope[list[FileMetaDataGet]],
    )
    async def _list_dataset_files_metadata(user_id: UserID, request: Request):
        assert "json_schema_extra" in FileMetaDataGet.model_config
        assert isinstance(FileMetaDataGet.model_config["json_schema_extra"], dict)
        assert isinstance(
            FileMetaDataGet.model_config["json_schema_extra"]["examples"], list
        )
        return Envelope[list[FileMetaDataGet]](
            data=[
                FileMetaDataGet.model_validate(e)
                for e in FileMetaDataGet.model_config["json_schema_extra"]["examples"]
            ]
        )

    app.include_router(router)

    return app


@pytest.fixture(scope="module")
def fake_storage_server(
    storage_vtag: str,
    fake_storage_app: FastAPI,
    # app_environment: EnvVarsDict,
) -> Iterator[URL]:
    storage_port = unused_port()
    with log_context(
        logging.INFO,
        msg=f"with fake storage server on 127.0.0.1:{storage_port}/{storage_vtag}",
    ) as ctx:
        config = uvicorn.Config(
            fake_storage_app,
            host="127.0.0.1",
            port=storage_port,
            log_level="error",
        )
        server = uvicorn.Server(config)

        thread = Thread(target=server.run)
        thread.daemon = True
        thread.start()

        ctx.logger.info(
            "health at : %s",
            f"http://127.0.0.1:{storage_port}/{storage_vtag}",
        )

        yield URL(f"http://127.0.0.1:{storage_port}")

        server.should_exit = True
        thread.join(timeout=10)


@pytest.fixture
def app_environment(
    storage_vtag: str,
    fake_storage_server: URL,
    app_environment: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, str]:
    # NOTE: overrides app_environment
    monkeypatch.setenv("STORAGE_PORT", f"{fake_storage_server.port}")
    monkeypatch.setenv("STORAGE_VTAG", storage_vtag)
    monkeypatch.setenv("WEBSERVER_GARBAGE_COLLECTOR", "null")
    return app_environment | {"WEBSERVER_GARBAGE_COLLECTOR": "null"}


# --------------------------------------------------------------------------
PREFIX = "/" + API_VERSION + "/storage"


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_200_OK),
        (UserRole.USER, status.HTTP_200_OK),
        (UserRole.TESTER, status.HTTP_200_OK),
    ],
)
async def test_list_storage_locations(
    client: TestClient,
    logged_user: dict[str, Any],
    expected: int,
):
    url = "/v0/storage/locations"
    assert url.startswith(PREFIX)

    resp = await client.get(url, params={"user_id": logged_user["id"]})
    data, error = await assert_status(resp, expected)

    if not error:
        assert "json_schema_extra" in FileLocation.model_config
        assert isinstance(FileLocation.model_config["json_schema_extra"], dict)
        assert isinstance(
            FileLocation.model_config["json_schema_extra"]["examples"], list
        )
        assert len(data) == len(
            FileLocation.model_config["json_schema_extra"]["examples"]
        )
        assert data == FileLocation.model_config["json_schema_extra"]["examples"]


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_200_OK),
        (UserRole.USER, status.HTTP_200_OK),
        (UserRole.TESTER, status.HTTP_200_OK),
    ],
)
async def test_list_datasets_metadata(
    client: TestClient,
    logged_user: dict[str, Any],
    expected: int,
):
    url = "/v0/storage/locations/0/datasets"
    assert url.startswith(PREFIX)
    assert client.app
    _url = client.app.router["list_datasets_metadata"].url_for(location_id="0")

    assert url == str(_url)

    resp = await client.get(url, params={"user_id": logged_user["id"]})
    data, error = await assert_status(resp, expected)

    if not error:
        assert "json_schema_extra" in DatasetMetaDataGet.model_config
        assert isinstance(DatasetMetaDataGet.model_config["json_schema_extra"], dict)
        assert isinstance(
            DatasetMetaDataGet.model_config["json_schema_extra"]["examples"], list
        )

        assert len(data) == len(
            DatasetMetaDataGet.model_config["json_schema_extra"]["examples"]
        )
        assert data == DatasetMetaDataGet.model_config["json_schema_extra"]["examples"]


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_200_OK),
        (UserRole.USER, status.HTTP_200_OK),
        (UserRole.TESTER, status.HTTP_200_OK),
    ],
)
async def test_list_dataset_files_metadata(
    client: TestClient,
    logged_user: dict[str, Any],
    expected: int,
):
    url = "/v0/storage/locations/0/datasets/N:asdfsdf/metadata"
    assert url.startswith(PREFIX)
    assert client.app
    _url = client.app.router["list_dataset_files_metadata"].url_for(
        location_id="0", dataset_id="N:asdfsdf"
    )

    assert url == str(_url)

    resp = await client.get(url, params={"user_id": logged_user["id"]})
    data, error = await assert_status(resp, expected)

    if not error:
        assert "json_schema_extra" in FileMetaDataGet.model_config
        assert isinstance(FileMetaDataGet.model_config["json_schema_extra"], dict)
        assert isinstance(
            FileMetaDataGet.model_config["json_schema_extra"]["examples"], list
        )
        assert len(data) == len(
            FileMetaDataGet.model_config["json_schema_extra"]["examples"]
        )
        assert data == [
            FileMetaDataGet.model_validate(e).model_dump(mode="json")
            for e in FileMetaDataGet.model_config["json_schema_extra"]["examples"]
        ]


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_200_OK),
        (UserRole.USER, status.HTTP_200_OK),
        (UserRole.TESTER, status.HTTP_200_OK),
    ],
)
async def test_storage_file_meta(
    client: TestClient,
    logged_user: dict[str, Any],
    expected: int,
    faker: Faker,
):
    # tests redirect of path with quotes in path
    file_id = f"{faker.uuid4()}/{faker.uuid4()}/a/b/c/d/e/dat"
    quoted_file_id = quote(file_id, safe="")
    url = f"/v0/storage/locations/0/files/{quoted_file_id}/metadata"

    assert url.startswith(PREFIX)

    resp = await client.get(url, params={"user_id": logged_user["id"]})
    data, error = await assert_status(resp, expected)

    if not error:
        assert "json_schema_extra" in FileMetaDataGet.model_config
        assert isinstance(FileMetaDataGet.model_config["json_schema_extra"], dict)
        assert isinstance(
            FileMetaDataGet.model_config["json_schema_extra"]["examples"], list
        )

        assert data
        model = FileMetaDataGet.model_validate(data)
        assert model


@pytest.mark.parametrize(
    "user_role,expected",
    [
        (UserRole.ANONYMOUS, status.HTTP_401_UNAUTHORIZED),
        (UserRole.GUEST, status.HTTP_200_OK),
        (UserRole.USER, status.HTTP_200_OK),
        (UserRole.TESTER, status.HTTP_200_OK),
    ],
)
async def test_storage_list_filter(
    client: TestClient,
    logged_user: dict[str, Any],
    expected: int,
):
    # tests composition of 2 queries
    file_id = "a/b/c/d/e/dat"
    url = "/v0/storage/locations/0/files/metadata?uuid_filter={}".format(
        quote(file_id, safe="")
    )

    assert url.startswith(PREFIX)

    resp = await client.get(url, params={"user_id": logged_user["id"]})
    data, error = await assert_status(resp, expected)

    if not error:
        assert "json_schema_extra" in FileMetaDataGet.model_config
        assert isinstance(FileMetaDataGet.model_config["json_schema_extra"], dict)
        assert isinstance(
            FileMetaDataGet.model_config["json_schema_extra"]["examples"], list
        )

        assert len(data) == 2
        for item in data:
            model = FileMetaDataGet.model_validate(item)
            assert model
