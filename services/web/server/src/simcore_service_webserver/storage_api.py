""" Storage subsystem's API: responsible of communication with storage service

"""
import asyncio
import logging
from typing import Any, AsyncGenerator

from aiohttp import ClientError, ClientSession, ClientTimeout, web
from models_library.api_schemas_storage import (
    FileLocation,
    FileLocationArray,
    FileMetaDataGet,
)
from models_library.generics import Envelope
from models_library.projects import ProjectID
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import ByteSize, parse_obj_as
from pydantic.types import PositiveInt
from servicelib.aiohttp.client_session import get_client_session
from servicelib.aiohttp.long_running_tasks.client import (
    LRTask,
    long_running_task_request,
)
from servicelib.logging_utils import log_context
from simcore_service_webserver.projects.project_models import ProjectDict
from simcore_service_webserver.projects.projects_utils import NodesMap
from yarl import URL

from .storage_settings import StorageSettings, get_plugin_settings

log = logging.getLogger(__name__)

TOTAL_TIMEOUT_TO_COPY_DATA_SECS = 60 * 60


def _get_storage_client(app: web.Application) -> tuple[ClientSession, URL]:
    settings: StorageSettings = get_plugin_settings(app)
    # storage service API endpoint
    endpoint = URL(settings.base_url)

    session = get_client_session(app)
    return session, endpoint


async def get_storage_locations(
    app: web.Application, user_id: UserID
) -> FileLocationArray:
    log.debug("getting %s accessible locations...", f"{user_id=}")
    session, api_endpoint = _get_storage_client(app)
    locations_url = (api_endpoint / "locations").with_query(user_id=user_id)
    async with session.get(f"{locations_url}") as response:
        response.raise_for_status()
        locations_enveloped = Envelope[FileLocationArray].parse_obj(
            await response.json()
        )
        assert locations_enveloped.data  # nosec
        log.info("%s can access %s", f"{user_id=}", f"{locations_enveloped.data=}")
        return locations_enveloped.data


async def get_project_total_size_simcore_s3(
    app: web.Application, user_id: UserID, project_uuid: ProjectID
) -> ByteSize:
    with log_context(
        log,
        logging.DEBUG,
        msg=f"getting {project_uuid=} total size in S3 for {user_id=}",
    ):
        # NOTE: datcore does not handle filtering and is too slow for this, so for now this is hard-coded
        user_accessible_locations = [FileLocation(name="simcore.s3", id=0)]
        session, api_endpoint = _get_storage_client(app)

        project_size_bytes = 0
        for location in user_accessible_locations:
            files_metadata_url = (
                api_endpoint / "locations" / f"{location.id}" / "files" / "metadata"
            ).with_query(user_id=user_id, uuid_filter=f"{project_uuid}")
            async with session.get(f"{files_metadata_url}") as response:
                response.raise_for_status()
                list_of_files_enveloped = Envelope[list[FileMetaDataGet]].parse_obj(
                    await response.json()
                )
                assert list_of_files_enveloped.data is not None  # nosec
            for file_metadata in list_of_files_enveloped.data:
                project_size_bytes += file_metadata.file_size
        project_size = parse_obj_as(ByteSize, project_size_bytes)
        log.info(
            "%s total size in S3 is %s",
            f"{project_uuid}",
            f"{project_size.human_readable()}",
        )
        return project_size


async def copy_data_folders_from_project(
    app: web.Application,
    source_project: ProjectDict,
    destination_project: ProjectDict,
    nodes_map: NodesMap,
    user_id: UserID,
) -> AsyncGenerator[LRTask, None]:
    session, api_endpoint = _get_storage_client(app)
    log.debug("Copying %d nodes", len(nodes_map))
    # /simcore-s3/folders:
    async for lr_task in long_running_task_request(
        session,
        (api_endpoint / "simcore-s3/folders").with_query(user_id=user_id),
        json=jsonable_encoder(
            {
                "source": source_project,
                "destination": destination_project,
                "nodes_map": nodes_map,
            }
        ),
        client_timeout=TOTAL_TIMEOUT_TO_COPY_DATA_SECS,
    ):
        yield lr_task


async def _delete(session, target_url):
    async with session.delete(target_url, ssl=False) as resp:
        log.info(
            "delete_data_folders_of_project request responded with status %s",
            resp.status,
        )
        # NOTE: context will automatically close connection


async def delete_data_folders_of_project(app, project_id, user_id):
    # SEE api/specs/storage/v0/openapi.yaml
    session, api_endpoint = _get_storage_client(app)
    url = (api_endpoint / f"simcore-s3/folders/{project_id}").with_query(
        user_id=user_id
    )

    await _delete(session, url)


async def delete_data_folders_of_project_node(
    app, project_id: str, node_id: str, user_id: PositiveInt
):
    # SEE api/specs/storage/v0/openapi.yaml
    session, api_endpoint = _get_storage_client(app)
    url = (api_endpoint / f"simcore-s3/folders/{project_id}").with_query(
        user_id=user_id, node_id=node_id
    )

    await _delete(session, url)


async def is_healthy(app: web.Application) -> bool:
    try:
        client, api_endpoint = _get_storage_client(app)
        await client.get(
            url=(api_endpoint / ""),
            raise_for_status=True,
            ssl=False,
            timeout=ClientTimeout(total=2, connect=1),
        )
        return True
    except (ClientError, asyncio.TimeoutError) as err:
        # ClientResponseError, ClientConnectionError, ClientPayloadError, InValidURL
        log.debug("Storage is NOT healthy: %s", err)
        return False


async def get_app_status(app: web.Application) -> dict[str, Any]:
    client, api_endpoint = _get_storage_client(app)

    data = {}
    async with client.get(
        url=api_endpoint / "status",
    ) as resp:
        payload = await resp.json()
        data = payload["data"]

    return data
