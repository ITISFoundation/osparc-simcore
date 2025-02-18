import asyncio
import logging
from typing import Annotated, Any, cast

from fastapi import APIRouter, Depends, FastAPI, Request
from models_library.api_schemas_long_running_tasks.base import TaskProgress
from models_library.api_schemas_long_running_tasks.tasks import TaskGet
from models_library.api_schemas_storage.rest.storage_schemas import (
    FileMetaDataGet,
    FoldersBody,
)
from models_library.generics import Envelope
from models_library.projects import ProjectID
from servicelib.aiohttp import status
from servicelib.fastapi.long_running_tasks._dependencies import get_tasks_manager
from servicelib.logging_utils import log_context
from servicelib.long_running_tasks._task import start_task
from settings_library.s3 import S3Settings
from yarl import URL

from ...dsm import get_dsm_provider
from ...models import (
    DeleteFolderQueryParams,
    FileMetaData,
    SearchFilesQueryParams,
    StorageQueryParamsBase,
)
from ...modules import sts
from ...simcore_s3_dsm import SimcoreS3DataManager

_logger = logging.getLogger(__name__)

router = APIRouter(
    tags=[
        "simcore-s3",
    ],
)


@router.post("/simcore-s3:access", response_model=Envelope[S3Settings])
async def get_or_create_temporary_s3_access(
    query_params: Annotated[StorageQueryParamsBase, Depends()],
    request: Request,
):
    # NOTE: the name of the method is not accurate, these are not temporary at all
    # it returns the credentials of the s3 backend!
    s3_settings: S3Settings = await sts.get_or_create_temporary_token_for_user(
        request.app, query_params.user_id
    )
    return Envelope[S3Settings](data=s3_settings)


async def _copy_folders_from_project(
    progress: TaskProgress,
    app: FastAPI,
    query_params: StorageQueryParamsBase,
    body: FoldersBody,
) -> Envelope[dict[str, Any]]:
    dsm = cast(
        SimcoreS3DataManager,
        get_dsm_provider(app).get(SimcoreS3DataManager.get_location_id()),
    )
    with log_context(
        _logger,
        logging.INFO,
        msg=f"copying {body.source['uuid']} -> {body.destination['uuid']}",
    ):
        await dsm.deep_copy_project_simcore_s3(
            query_params.user_id,
            body.source,
            body.destination,
            body.nodes_map,
            task_progress=progress,
        )

    return Envelope[dict[str, Any]](data=body.destination)


@router.post(
    "/simcore-s3/folders",
    response_model=Envelope[TaskGet],
    status_code=status.HTTP_202_ACCEPTED,
)
async def copy_folders_from_project(
    query_params: Annotated[StorageQueryParamsBase, Depends()],
    body: FoldersBody,
    request: Request,
):
    task_id = None
    try:
        task_id = start_task(
            get_tasks_manager(request),
            _copy_folders_from_project,
            app=request.app,
            query_params=query_params,
            body=body,
        )
        relative_url = URL(f"{request.url}").relative()

        return Envelope[TaskGet](
            data=TaskGet(
                task_id=task_id,
                task_name=f"{request.method} {relative_url}",
                status_href=f"{request.url_for('get_task_status', task_id=task_id)}",
                result_href=f"{request.url_for('get_task_result', task_id=task_id)}",
                abort_href=f"{request.url_for('cancel_and_delete_task', task_id=task_id)}",
            )
        )
    except asyncio.CancelledError:
        if task_id:
            await get_tasks_manager(request).cancel_task(
                task_id, with_task_context=None
            )
        raise


@router.delete(
    "/simcore-s3/folders/{folder_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_folders_of_project(
    query_params: Annotated[DeleteFolderQueryParams, Depends()],
    folder_id: str,
    request: Request,
):
    dsm = cast(
        SimcoreS3DataManager,
        get_dsm_provider(request.app).get(SimcoreS3DataManager.get_location_id()),
    )
    await dsm.delete_project_simcore_s3(
        query_params.user_id,
        ProjectID(folder_id),
        query_params.node_id,
    )


@router.post(
    "/simcore-s3/files/metadata:search",
    response_model=Envelope[list[FileMetaDataGet]],
)
async def search_files(
    query_params: Annotated[SearchFilesQueryParams, Depends()], request: Request
):
    dsm = cast(
        SimcoreS3DataManager,
        get_dsm_provider(request.app).get(SimcoreS3DataManager.get_location_id()),
    )

    data: list[FileMetaData] = await dsm.search_owned_files(
        user_id=query_params.user_id,
        file_id_prefix=query_params.startswith,
        sha256_checksum=query_params.sha256_checksum,
        limit=query_params.limit,
        offset=query_params.offset,
    )
    _logger.debug(
        "Found %d files starting with '%s'",
        len(data),
        f"{query_params.startswith=}, {query_params.sha256_checksum=}",
    )
    return Envelope[list[FileMetaDataGet]](
        data=[FileMetaDataGet(**d.model_dump()) for d in data]
    )
