import datetime
import logging
import mimetypes
import urllib.parse
from typing import Final

from aiohttp import web
from aiohttp.client import ClientError
from models_library.api_schemas_storage import FileMetaDataGet
from models_library.projects import ProjectID
from models_library.projects_nodes import Node, NodeID
from models_library.projects_nodes_io import SimCoreFileLink
from models_library.users import UserID
from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
    NonNegativeFloat,
    NonNegativeInt,
    ValidationError,
    parse_obj_as,
    root_validator,
)
from servicelib.utils import logged_gather

from .._constants import RQT_USERID_KEY
from ..application_settings import get_settings
from ..storage.api import get_download_link, get_files_in_node_folder
from .exceptions import ProjectStartsTooManyDynamicNodesError

_logger = logging.getLogger(__name__)

_NODE_START_INTERVAL_S: Final[datetime.timedelta] = datetime.timedelta(seconds=15)

_SUPPORTED_THUMBNAIL_EXTENSIONS: set[str] = {".png", ".jpeg", ".jpg"}

ASSETS_FOLDER: Final[str] = "assets"


def get_service_start_lock_key(user_id: UserID, project_uuid: ProjectID) -> str:
    return f"lock_service_start_limit.{user_id}.{project_uuid}"


def check_num_service_per_projects_limit(
    app: web.Application,
    number_of_services: int,
    user_id: UserID,
    project_uuid: ProjectID,
) -> None:
    """
    raises ProjectStartsTooManyDynamicNodes if the user cannot start more services
    """
    project_settings = get_settings(app).WEBSERVER_PROJECTS
    assert project_settings  # nosec
    if project_settings.PROJECTS_MAX_NUM_RUNNING_DYNAMIC_NODES > 0 and (
        number_of_services >= project_settings.PROJECTS_MAX_NUM_RUNNING_DYNAMIC_NODES
    ):
        raise ProjectStartsTooManyDynamicNodesError(
            user_id=user_id, project_uuid=project_uuid
        )


def get_total_project_dynamic_nodes_creation_interval(
    max_nodes: NonNegativeInt,
) -> NonNegativeFloat:
    """
    Estimated amount of time for all project node creation requests to be sent to the
    director-v2. Note: these calls are sent one after the other.
    """
    return max_nodes * _NODE_START_INTERVAL_S.total_seconds()


#
# PREVIEWS
#


class NodeScreenshot(BaseModel):
    thumbnail_url: HttpUrl
    file_url: HttpUrl
    mimetype: str | None = Field(
        default=None,
        description="File's media type or None if unknown. SEE https://www.iana.org/assignments/media-types/media-types.xhtml",
        example="image/jpeg",
    )

    @root_validator(pre=True)
    @classmethod
    def guess_mimetype_if_undefined(cls, values):
        mimetype = values.get("mimetype")

        if mimetype is None:
            file_url = values["file_url"]
            assert file_url  # nosec

            _type, _encoding = mimetypes.guess_type(file_url)
            # NOTE: mimetypes.guess_type works differently in our image, therefore made it nullable if
            # cannot guess type
            # SEE https://github.com/ITISFoundation/osparc-simcore/issues/4385
            values["mimetype"] = _type

        return values


def __get_search_key(meta_data: FileMetaDataGet) -> str:
    return f"{meta_data.file_id}".lower()


def _get_files_with_thumbnails(
    assets_files: list[FileMetaDataGet],
) -> list[tuple[FileMetaDataGet, FileMetaDataGet]]:
    """returns a list of tuples where the second entry is the thumbnails"""

    search_file_name_to_file_meta_data_get: dict[str, FileMetaDataGet] = {
        __get_search_key(f): f
        for f in assets_files
        if not f.file_id.endswith(".hidden_do_not_remove")  # TODO: remove this line
    }

    with_thumbnail_image: list[tuple[FileMetaDataGet, FileMetaDataGet]] = []

    for search_file_name in search_file_name_to_file_meta_data_get:
        # search for thumbnail
        thumbnail: FileMetaDataGet | None = None
        for extension in _SUPPORTED_THUMBNAIL_EXTENSIONS:
            thumbnail_search_file_name = f"{search_file_name}{extension}"
            if thumbnail_search_file_name in search_file_name_to_file_meta_data_get:
                thumbnail = search_file_name_to_file_meta_data_get[
                    thumbnail_search_file_name
                ]
                break

        if thumbnail:
            # do something with it emit an entry
            with_thumbnail_image.append(
                (search_file_name_to_file_meta_data_get[search_file_name], thumbnail)
            )

    # remove entries which have been associated
    for file_meta, thumbnail_meta in with_thumbnail_image:
        search_file_name_to_file_meta_data_get.pop(__get_search_key(file_meta), None)
        search_file_name_to_file_meta_data_get.pop(
            __get_search_key(thumbnail_meta), None
        )

    without_thumbnail_image = [
        (x, x) for x in search_file_name_to_file_meta_data_get.values()
    ]

    return with_thumbnail_image + without_thumbnail_image


async def _get_http_url(
    app: web.Application, user_id: UserID, file_meta_data: FileMetaDataGet
) -> tuple[str, HttpUrl]:
    return __get_search_key(file_meta_data), await get_download_link(
        app,
        user_id,
        parse_obj_as(SimCoreFileLink, {"store": "0", "path": file_meta_data.file_id}),
    )


async def _to_http_urls_parallel(
    app: web.Application,
    user_id: UserID,
    entries: list[tuple[FileMetaDataGet, FileMetaDataGet]],
) -> list[tuple[HttpUrl, HttpUrl]]:
    search_map: dict[str, FileMetaDataGet] = {}

    for file_meta_data, thumbnail_meta_data in entries:
        search_map[__get_search_key(file_meta_data)] = file_meta_data
        search_map[__get_search_key(thumbnail_meta_data)] = thumbnail_meta_data

    results = await logged_gather(
        *[_get_http_url(app, user_id, x) for x in search_map.values()],
        max_concurrency=10,
    )

    mapped_http_url: dict[str, HttpUrl] = dict(results)

    return [
        (
            mapped_http_url[__get_search_key(t[0])],
            mapped_http_url[__get_search_key(t[1])],
        )
        for t in entries
    ]


async def get_node_screenshots(
    request: web.Request,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    node: Node,
) -> list[NodeScreenshot]:
    screenshots: list[NodeScreenshot] = []

    if (
        "file-picker" in node.key
        and "fake" in node.label.lower()
        and node.outputs is not None
    ):
        # Example of file that can be added in file-picker:
        # Example https://github.com/Ybalrid/Ogre_glTF/raw/6a59adf2f04253a3afb9459549803ab297932e8d/Media/Monster.glb
        try:
            user_id = request[RQT_USERID_KEY]
            text = urllib.parse.quote(node.label)

            assert node.outputs is not None  # nosec

            filelink = parse_obj_as(SimCoreFileLink, node.outputs["outFile"])

            file_url = await get_download_link(request.app, user_id, filelink)
            screenshots.append(
                NodeScreenshot(
                    thumbnail_url=f"https://placehold.co/170x120?text={text}",  # type: ignore[arg-type]
                    file_url=file_url,
                )
            )
        except (KeyError, ValidationError, ClientError) as err:
            _logger.warning(
                "Skipping fake node. Unable to create link from file-picker %s: %s",
                node.json(indent=1),
                err,
            )

    elif node.key.startswith("simcore/services/dynamic"):
        # when dealing with dynamic service scan the assets directory and
        # pull in all the assets that have been dropped in there

        assets_files: list[FileMetaDataGet] = await get_files_in_node_folder(
            app=request.app,
            user_id=user_id,
            project_id=project_id,
            node_id=node_id,
            folder_name=ASSETS_FOLDER,
        )

        asset_files_with_thumbnails: list[
            tuple[FileMetaDataGet, FileMetaDataGet]
        ] = _get_files_with_thumbnails(assets_files)

        asset_file_urls_with_thumbnails: list[
            tuple[HttpUrl, HttpUrl]
        ] = await _to_http_urls_parallel(
            app=request.app, user_id=user_id, entries=asset_files_with_thumbnails
        )

        for file_url, thumbnail_url in asset_file_urls_with_thumbnails:
            screenshots.append(
                NodeScreenshot(thumbnail_url=thumbnail_url, file_url=file_url)
            )

    return screenshots
