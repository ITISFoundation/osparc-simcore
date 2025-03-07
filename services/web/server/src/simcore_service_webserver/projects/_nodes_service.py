import datetime
import logging
import mimetypes
import urllib.parse
from pathlib import Path
from pprint import pformat
from typing import Any, Final, NamedTuple

from aiohttp import web
from aiohttp.client import ClientError
from common_library.json_serialization import json_dumps
from models_library.api_schemas_storage.storage_schemas import FileMetaDataGet
from models_library.basic_types import KeyIDStr
from models_library.projects import ProjectID
from models_library.projects_nodes import Node, PartialNode
from models_library.projects_nodes_io import NodeID, NodeIDStr, SimCoreFileLink
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.users import UserID
from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
    NonNegativeFloat,
    NonNegativeInt,
    ValidationError,
    model_validator,
)
from servicelib.logging_utils import get_log_record_extra
from servicelib.utils import logged_gather

from ..application_settings import get_application_settings
from ..storage import api as storage_service
from . import _access_rights_service, _nodes_repository
from ._projects_repository_legacy import APP_PROJECT_DBAPI, ProjectDBAPI
from .exceptions import ProjectStartsTooManyDynamicNodesError

_logger = logging.getLogger(__name__)

_NODE_START_INTERVAL_S: Final[datetime.timedelta] = datetime.timedelta(seconds=15)

_SUPPORTED_THUMBNAIL_EXTENSIONS: set[str] = {".png", ".jpeg", ".jpg"}
_SUPPORTED_PREVIEW_FILE_EXTENSIONS: set[str] = {".gltf", ".png", ".jpeg", ".jpg"}

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
    project_settings = get_application_settings(app).WEBSERVER_PROJECTS
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


async def get_project_nodes_services(
    app: web.Application, *, project_uuid: ProjectID
) -> list[tuple[ServiceKey, ServiceVersion]]:
    return await _nodes_repository.get_project_nodes_services(
        app, project_uuid=project_uuid
    )


#
# PREVIEWS
#


def _guess_mimetype_from_name(name: str) -> str | None:
    """Tries to guess the mimetype provided a name

    Arguments:
        name -- path of a file or the file url
    """
    _type, _ = mimetypes.guess_type(name)
    # NOTE: mimetypes.guess_type works differently in our image, therefore made it nullable if
    # cannot guess type
    # SEE https://github.com/ITISFoundation/osparc-simcore/issues/4385
    return _type


class NodeScreenshot(BaseModel):
    thumbnail_url: HttpUrl
    file_url: HttpUrl
    mimetype: str | None = Field(
        default=None,
        description="File's media type or None if unknown. SEE https://www.iana.org/assignments/media-types/media-types.xhtml",
        examples=["image/jpeg"],
    )

    @model_validator(mode="before")
    @classmethod
    def guess_mimetype_if_undefined(cls, values):
        mimetype = values.get("mimetype")

        if mimetype is None:
            file_url = values["file_url"]
            assert file_url  # nosec

            values["mimetype"] = _guess_mimetype_from_name(file_url)

        return values


def __get_search_key(meta_data: FileMetaDataGet) -> str:
    return f"{meta_data.file_id}".lower()


class _FileWithThumbnail(NamedTuple):
    file: FileMetaDataGet
    thumbnail: FileMetaDataGet


def _get_files_with_thumbnails(
    assets_files: list[FileMetaDataGet],
) -> list[_FileWithThumbnail]:
    """returns a list of tuples where the second entry is the thumbnails"""

    selected_file_entries: dict[str, FileMetaDataGet] = {
        __get_search_key(f): f
        for f in assets_files
        if not f.file_id.endswith(".hidden_do_not_remove")
        and Path(f.file_id).suffix.lower() in _SUPPORTED_PREVIEW_FILE_EXTENSIONS
    }

    with_thumbnail_image: list[_FileWithThumbnail] = []

    for selected_file in set(selected_file_entries.keys()):
        # search for thumbnail
        thumbnail: FileMetaDataGet | None = None
        for extension in _SUPPORTED_THUMBNAIL_EXTENSIONS:
            thumbnail_search_file_name = f"{selected_file}{extension}"
            if thumbnail_search_file_name in selected_file_entries:
                thumbnail = selected_file_entries[thumbnail_search_file_name]
                break
        if not thumbnail:
            continue

        # since there is a thumbnail it can be associated to a file
        with_thumbnail_image.append(
            _FileWithThumbnail(
                file=selected_file_entries[selected_file],
                thumbnail=thumbnail,
            )
        )
        # remove entries which have been used
        selected_file_entries.pop(
            __get_search_key(selected_file_entries[selected_file]), None
        )
        selected_file_entries.pop(__get_search_key(thumbnail), None)

    no_thumbnail_image: list[_FileWithThumbnail] = [
        _FileWithThumbnail(file=x, thumbnail=x) for x in selected_file_entries.values()
    ]

    return with_thumbnail_image + no_thumbnail_image


async def __get_link(
    app: web.Application, user_id: UserID, file_meta_data: FileMetaDataGet
) -> tuple[str, HttpUrl]:
    return __get_search_key(file_meta_data), await storage_service.get_download_link(
        app,
        user_id,
        SimCoreFileLink.model_validate({"store": "0", "path": file_meta_data.file_id}),
    )


async def _get_node_screenshots(
    app: web.Application,
    user_id: UserID,
    files_with_thumbnails: list[_FileWithThumbnail],
) -> list[NodeScreenshot]:
    """resolves links concurrently before returning all the NodeScreenshots"""

    search_map: dict[str, FileMetaDataGet] = {}

    for entry in files_with_thumbnails:
        search_map[__get_search_key(entry.file)] = entry.file
        search_map[__get_search_key(entry.thumbnail)] = entry.thumbnail

    resolved_links: list[tuple[str, HttpUrl]] = await logged_gather(
        *[__get_link(app, user_id, x) for x in search_map.values()],
        max_concurrency=10,
    )

    mapped_http_url: dict[str, HttpUrl] = dict(resolved_links)

    return [
        NodeScreenshot(
            mimetype=_guess_mimetype_from_name(e.file.file_id),
            file_url=mapped_http_url[__get_search_key(e.file)],
            thumbnail_url=mapped_http_url[__get_search_key(e.thumbnail)],
        )
        for e in files_with_thumbnails
    ]


async def get_node_screenshots(
    app: web.Application,
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
            text = urllib.parse.quote(node.label)

            assert node.outputs is not None  # nosec

            filelink = SimCoreFileLink.model_validate(node.outputs[KeyIDStr("outFile")])

            file_url = await storage_service.get_download_link(app, user_id, filelink)
            screenshots.append(
                NodeScreenshot(
                    thumbnail_url=f"https://placehold.co/170x120?text={text}",  # type: ignore[arg-type]
                    file_url=file_url,
                )
            )
        except (KeyError, ValidationError, ClientError) as err:
            _logger.warning(
                "Skipping fake node. Unable to create link from file-picker %s: %s",
                node.model_dump_json(indent=1),
                err,
            )

    elif node.key.startswith("simcore/services/dynamic"):
        # when dealing with dynamic service scan the assets directory and
        # pull in all the assets that have been dropped in there

        assets_files: list[FileMetaDataGet] = (
            await storage_service.get_files_in_node_folder(
                app=app,
                user_id=user_id,
                project_id=project_id,
                node_id=node_id,
                folder_name=ASSETS_FOLDER,
            )
        )

        resolved_screenshots: list[NodeScreenshot] = await _get_node_screenshots(
            app=app,
            user_id=user_id,
            files_with_thumbnails=_get_files_with_thumbnails(assets_files),
        )
        screenshots.extend(resolved_screenshots)

    return screenshots


async def project_get_depending_nodes(
    project: dict[str, Any], node_uuid: NodeID
) -> set[NodeID]:
    depending_node_uuids = set()
    for dep_node_uuid, dep_node_data in project.get("workbench", {}).items():
        for dep_node_inputs_key_data in dep_node_data.get("inputs", {}).values():
            if (
                isinstance(dep_node_inputs_key_data, dict)
                and dep_node_inputs_key_data.get("nodeUuid") == f"{node_uuid}"
            ):
                depending_node_uuids.add(NodeID(dep_node_uuid))

    return depending_node_uuids


async def update_project_node_outputs(
    app: web.Application,
    user_id: UserID,
    project_id: ProjectID,
    node_id: NodeID,
    new_outputs: dict | None,
    new_run_hash: str | None,
) -> tuple[dict, list[str]]:
    """
    Updates outputs of a given node in a project with 'data'
    """
    _logger.debug(
        "updating node %s outputs in project %s for user %s with %s: run_hash [%s]",
        node_id,
        project_id,
        user_id,
        json_dumps(new_outputs),
        new_run_hash,
        extra=get_log_record_extra(user_id=user_id),
    )
    new_outputs = new_outputs or {}

    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]
    product_name = await db.get_project_product(project_id)
    await _access_rights_service.check_user_project_permission(
        app,
        project_id=project_id,
        user_id=user_id,
        product_name=product_name,
        permission="write",  # NOTE: MD: before only read was sufficient, double check this
    )

    updated_project, changed_entries = await db.update_project_node_data(
        user_id=user_id,
        project_uuid=project_id,
        node_id=node_id,
        product_name=None,
        new_node_data={"outputs": new_outputs, "runHash": new_run_hash},
    )

    await _nodes_repository.update(
        app,
        project_id=project_id,
        node_id=node_id,
        partial_node=PartialNode.model_construct(
            outputs=new_outputs, run_hash=new_run_hash
        ),
    )

    _logger.debug(
        "patched project %s, following entries changed: %s",
        project_id,
        pformat(changed_entries),
    )

    # changed entries come in the form of {node_uuid: {outputs: {changed_key1: value1, changed_key2: value2}}}
    # we do want only the key names
    changed_keys = (
        changed_entries.get(NodeIDStr(f"{node_id}"), {}).get("outputs", {}).keys()
    )
    return updated_project, changed_keys


async def list_node_ids_in_project(
    app: web.Application,
    project_uuid: ProjectID,
) -> set[NodeID]:
    """Returns a set with all the node_ids from a project's workbench"""
    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]
    return await db.list_node_ids_in_project(project_uuid)


async def is_node_id_present_in_any_project_workbench(
    app: web.Application,
    node_id: NodeID,
) -> bool:
    """If the node_id is presnet in one of the projects' workbenche returns True"""
    db: ProjectDBAPI = app[APP_PROJECT_DBAPI]
    return await db.node_id_exists(node_id)
