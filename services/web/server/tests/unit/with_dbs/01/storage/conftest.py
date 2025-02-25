# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import logging
import random
from collections.abc import Iterator
from pathlib import Path
from threading import Thread
from typing import Annotated

import pytest
import uvicorn
from faker import Faker
from fastapi import APIRouter, Depends, FastAPI, Request, status
from fastapi_pagination import add_pagination, create_page
from fastapi_pagination.cursor import CursorPage, CursorParams
from models_library.api_schemas_storage.storage_schemas import (
    DatasetMetaDataGet,
    FileLocation,
    FileMetaDataGet,
    FileMetaDataGetv010,
    FileUploadCompleteResponse,
    FileUploadCompletionBody,
    FileUploadSchema,
    LinkType,
    PathMetaDataGet,
)
from models_library.generics import Envelope
from models_library.projects import ProjectID
from models_library.projects_nodes_io import LocationID, StorageFileID
from models_library.users import UserID
from pydantic import AnyUrl, TypeAdapter
from pytest_simcore.helpers.logging_tools import log_context
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from servicelib.utils import unused_port
from yarl import URL


@pytest.fixture(scope="session")
def storage_vtag() -> str:
    return "v9"


@pytest.fixture(scope="module")
def fake_storage_app(storage_vtag: str) -> FastAPI:  # noqa: C901
    app = FastAPI(debug=True)
    add_pagination(app)

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
        "/locations/{location_id}/paths",
        response_model=CursorPage[PathMetaDataGet],
    )
    async def _list_paths(
        page_params: Annotated[CursorParams, Depends()],
        # dsm: Annotated[BaseDataManager, Depends(get_data_manager)],
        user_id: UserID,
        file_filter: Path | None = None,
    ):
        assert user_id
        assert "json_schema_extra" in PathMetaDataGet.model_config
        assert isinstance(PathMetaDataGet.model_config["json_schema_extra"], dict)
        assert isinstance(
            PathMetaDataGet.model_config["json_schema_extra"]["examples"], list
        )

        example_index = len(file_filter.parts) if file_filter else 0
        assert example_index < len(
            PathMetaDataGet.model_config["json_schema_extra"]["examples"]
        ), "fake server unable to server this example"
        chosen_example = PathMetaDataGet.model_config["json_schema_extra"]["examples"][
            example_index
        ]

        return create_page(
            random.randint(3, 15) * [PathMetaDataGet.model_validate(chosen_example)],
            params=page_params,
            next_=None,
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

        if uuid_filter:
            return Envelope[list[FileMetaDataGet]](
                data=random.sample(
                    [
                        FileMetaDataGet.model_validate(e)
                        for e in FileMetaDataGet.model_json_schema()["examples"]
                    ],
                    2,
                )
            )
        return Envelope[list[FileMetaDataGet]](
            data=[
                FileMetaDataGet.model_validate(e)
                for e in FileMetaDataGet.model_json_schema()["examples"]
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

        return Envelope[FileMetaDataGet](
            data=random.choice(  # noqa: S311
                [
                    FileMetaDataGet.model_validate(e)
                    for e in FileMetaDataGet.model_json_schema()["examples"]
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

        return Envelope[list[FileMetaDataGet]](
            data=[
                FileMetaDataGet.model_validate(e)
                for e in FileMetaDataGet.model_json_schema()["examples"]
            ]
        )

    @router.put(
        "/locations/{location_id}/files/{file_id:path}",
        response_model=Envelope[FileUploadSchema],
    )
    async def upload_file(
        user_id: UserID,
        location_id: LocationID,
        file_id: StorageFileID,
        request: Request,
        link_type: LinkType = LinkType.PRESIGNED,
    ):
        assert "json_schema_extra" in FileUploadSchema.model_config

        abort_url = (
            URL(f"{request.url}")
            .with_path(
                request.app.url_path_for(
                    "abort_upload_file",
                    location_id=f"{location_id}",
                    file_id=file_id,
                )
            )
            .with_query(user_id=user_id)
        )

        complete_url = (
            URL(f"{request.url}")
            .with_path(
                request.app.url_path_for(
                    "complete_upload_file",
                    location_id=f"{location_id}",
                    file_id=file_id,
                )
            )
            .with_query(user_id=user_id)
        )
        response = FileUploadSchema.model_validate(
            random.choice(  # noqa: S311
                FileUploadSchema.model_json_schema()["examples"]
            )
        )
        response.links.abort_upload = TypeAdapter(AnyUrl).validate_python(
            f"{abort_url}"
        )
        response.links.complete_upload = TypeAdapter(AnyUrl).validate_python(
            f"{complete_url}"
        )

        return Envelope[FileUploadSchema](data=response)

    @router.post(
        "/locations/{location_id}/files/{file_id:path}:complete",
        response_model=Envelope[FileUploadCompleteResponse],
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def complete_upload_file(
        user_id: UserID,
        location_id: LocationID,
        file_id: StorageFileID,
        body: FileUploadCompletionBody,
        request: Request,
    ):
        ...

    @router.post(
        "/locations/{location_id}/files/{file_id:path}:abort",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    async def abort_upload_file(
        user_id: UserID,
        location_id: LocationID,
        file_id: StorageFileID,
        request: Request,
    ):
        ...

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

    return app_environment | setenvs_from_dict(
        monkeypatch,
        {
            "STORAGE_PORT": f"{fake_storage_server.port}",
            "STORAGE_VTAG": storage_vtag,
            "WEBSERVER_DB_LISTENER": "0",
            "WEBSERVER_GARBAGE_COLLECTOR": "null",
        },
    )


@pytest.fixture
def location_id(faker: Faker) -> LocationID:
    return TypeAdapter(LocationID).validate_python(faker.pyint(min_value=0))
