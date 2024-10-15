""" Storage subsystem's API: responsible of communication with storage service

"""

import asyncio
import logging
import urllib.parse
from collections.abc import AsyncGenerator
from typing import Any, Final

from aiohttp import ClientError, ClientSession, ClientTimeout, web
from models_library.api_schemas_storage import (
    FileLocation,
    FileLocationArray,
    FileMetaDataGet,
    PresignedLink,
)
from models_library.generics import Envelope
from models_library.projects import ProjectID
from models_library.projects_nodes_io import LocationID, NodeID, SimCoreFileLink
from models_library.users import UserID
from models_library.utils.fastapi_encoders import jsonable_encoder
from pydantic import ByteSize, HttpUrl, TypeAdapter
from servicelib.aiohttp.client_session import get_client_session
from servicelib.aiohttp.long_running_tasks.client import (
    LRTask,
    long_running_task_request,
)
from servicelib.logging_utils import get_log_record_extra, log_context
from yarl import URL

from ..projects.models import ProjectDict
from ..projects.utils import NodesMap
from .settings import StorageSettings, get_plugin_settings

_logger = logging.getLogger(__name__)

_TOTAL_TIMEOUT_TO_COPY_DATA_SECS: Final[int] = 60 * 60
_SIMCORE_LOCATION: Final[LocationID] = 0


def _get_storage_client(app: web.Application) -> tuple[ClientSession, URL]:
    settings: StorageSettings = get_plugin_settings(app)
    # storage service API endpoint
    endpoint = URL(settings.base_url)

    session = get_client_session(app)
    return session, endpoint


async def get_storage_locations(
    app: web.Application, user_id: UserID
) -> FileLocationArray:
    _logger.debug("getting %s accessible locations...", f"{user_id=}")
    session, api_endpoint = _get_storage_client(app)
    locations_url = (api_endpoint / "locations").with_query(user_id=user_id)
    async with session.get(f"{locations_url}") as response:
        response.raise_for_status()
        locations_enveloped = Envelope[FileLocationArray].model_validate(
            await response.json()
        )
        assert locations_enveloped.data  # nosec
        _logger.info(
            "%s can access %s",
            f"{user_id=}",
            f"{locations_enveloped.data=}",
            extra=get_log_record_extra(user_id=user_id),
        )
        return locations_enveloped.data


async def get_project_total_size_simcore_s3(
    app: web.Application, user_id: UserID, project_uuid: ProjectID
) -> ByteSize:
    with log_context(
        _logger,
        logging.DEBUG,
        msg=f"getting {project_uuid=} total size in S3 for {user_id=}",
        extra=get_log_record_extra(user_id=user_id),
    ):
        # NOTE: datcore does not handle filtering and is too slow for this, so for now this is hard-coded
        user_accessible_locations = [FileLocation(name="simcore.s3", id=0)]
        session, api_endpoint = _get_storage_client(app)

        project_size_bytes = 0
        for location in user_accessible_locations:
            files_metadata_url = (
                api_endpoint / "locations" / f"{location.id}" / "files" / "metadata"
            ).with_query(user_id=user_id, project_id=f"{project_uuid}")
            async with session.get(f"{files_metadata_url}") as response:
                response.raise_for_status()
                list_of_files_enveloped = Envelope[
                    list[FileMetaDataGet]
                ].model_validate(await response.json())
                assert list_of_files_enveloped.data is not None  # nosec
            project_size_bytes += sum(
                file_metadata.file_size
                for file_metadata in list_of_files_enveloped.data
            )
        return TypeAdapter(ByteSize).validate_python(project_size_bytes)


async def copy_data_folders_from_project(
    app: web.Application,
    source_project: ProjectDict,
    destination_project: ProjectDict,
    nodes_map: NodesMap,
    user_id: UserID,
) -> AsyncGenerator[LRTask, None]:
    session, api_endpoint = _get_storage_client(app)
    _logger.debug("Copying %d nodes", len(nodes_map))
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
        client_timeout=_TOTAL_TIMEOUT_TO_COPY_DATA_SECS,
    ):
        yield lr_task


async def _delete(session, target_url):
    async with session.delete(target_url, ssl=False) as resp:
        _logger.info(
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
    app, project_id: str, node_id: str, user_id: UserID
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
        _logger.debug("Storage is NOT healthy: %s", err)
        return False


async def get_app_status(app: web.Application) -> dict[str, Any]:
    client, api_endpoint = _get_storage_client(app)

    async with client.get(
        url=api_endpoint / "status",
    ) as resp:
        data: dict[str, Any] = (await resp.json())["data"]
        assert isinstance(data, dict)  # nosec
        return data


async def get_download_link(
    app: web.Application, user_id: UserID, filelink: SimCoreFileLink
) -> HttpUrl:
    """
    Raises:
        ClientError
        ValidationError

    Returns:
        A pre-signed link for simcore file-links (i.e. provide in file-picker's outputs['outFile'])
    """
    session, api_endpoint = _get_storage_client(app)
    url = (
        api_endpoint
        / f"locations/{filelink.store}/files"
        / urllib.parse.quote(filelink.path, safe="")
    ).with_query(user_id=user_id)

    async with session.get(f"{url}") as response:
        response.raise_for_status()
        download: PresignedLink | None = (
            Envelope[PresignedLink].model_validate(await response.json()).data
        )
        assert download is not None  # nosec
        link: HttpUrl = TypeAdapter(HttpUrl).validate_python(download.link)
        return link


async def get_files_in_node_folder(
    app: web.Application,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    folder_name: str,
) -> list[FileMetaDataGet]:
    session, api_endpoint = _get_storage_client(app)

    s3_folder_path = f"{project_id}/{node_id}/{folder_name}"
    files_metadata_url = (
        api_endpoint / "locations" / f"{_SIMCORE_LOCATION}" / "files" / "metadata"
    ).with_query(user_id=user_id, uuid_filter=s3_folder_path, expand_dirs="true")

    async with session.get(f"{files_metadata_url}") as response:
        response.raise_for_status()
        list_of_files_enveloped = Envelope[list[FileMetaDataGet]].model_validate(
            await response.json()
        )
        assert list_of_files_enveloped.data is not None  # nosec
        result: list[FileMetaDataGet] = list_of_files_enveloped.data
        return result
