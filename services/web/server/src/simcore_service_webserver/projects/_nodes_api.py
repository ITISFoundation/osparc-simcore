import datetime
import logging
import mimetypes
import urllib.parse
from typing import Final

from aiohttp import web
from aiohttp.client import ClientError
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

from .._constants import APP_SETTINGS_KEY, RQT_USERID_KEY
from ..application_settings import get_settings
from ..storage.api import get_download_link
from .exceptions import ProjectStartsTooManyDynamicNodesError

_logger = logging.getLogger(__name__)
_NODE_START_INTERVAL_S: Final[datetime.timedelta] = datetime.timedelta(seconds=15)


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


async def fake_screenshots_factory(
    request: web.Request, node_id: NodeID, node: Node
) -> list[NodeScreenshot]:
    """
    ONLY for testing purposes

    """
    assert request.app[APP_SETTINGS_KEY].WEBSERVER_DEV_FEATURES_ENABLED  # nosec
    screenshots = []

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
                    thumbnail_url=f"https://placehold.co/170x120?text={text}",
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
        # For dynamic services, just create fake images

        # References:
        # - https://github.com/Ybalrid/Ogre_glTF
        # - https://placehold.co/
        # - https://picsum.photos/
        #
        count = int(str(node_id.int)[0])
        text = urllib.parse.quote(node.label)

        screenshots = [
            *(
                NodeScreenshot(
                    thumbnail_url=f"https://picsum.photos/seed/{node_id.int + n}/170/120",
                    file_url=f"https://picsum.photos/seed/{node_id.int + n}/500",
                    mimetype="image/jpeg",
                )
                for n in range(count)
            ),
            *(
                NodeScreenshot(
                    thumbnail_url=f"https://placehold.co/170x120?text={text}",
                    file_url=f"https://placehold.co/500x500?text={text}",
                    mimetype="image/svg+xml",
                )
                for n in range(count)
            ),
        ]

    return screenshots
