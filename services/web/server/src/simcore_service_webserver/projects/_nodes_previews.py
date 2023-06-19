import logging
import mimetypes

from aiohttp import web
from models_library.projects_nodes import Node, NodeID
from models_library.projects_nodes_io import SimCoreFileLink
from pydantic import (
    BaseModel,
    Field,
    HttpUrl,
    ValidationError,
    parse_obj_as,
    root_validator,
)

from .._constants import APP_SETTINGS_KEY, RQT_USERID_KEY
from ..storage.api import get_download_link

_logger = logging.getLogger(__name__)


class NodeScreenshot(BaseModel):
    thumbnail_url: HttpUrl
    file_url: HttpUrl
    mimetype: str = Field(
        default=None,
        description="File's media type. SEE https://www.iana.org/assignments/media-types/media-types.xhtml",
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
            if _type is None:
                raise ValueError(
                    f"Failed to guess mimetype from {file_url=}. Must be explicitly defined."
                )

            values["mimetype"] = _type

        return values


async def fake_screenshots_factory(
    request: web.Request, node_id: NodeID, node: Node
) -> list[NodeScreenshot]:
    """
    ONLY for testing purposes

    """
    assert request.app[APP_SETTINGS_KEY].WEBSERVER_DEV_FEATURES_ENABLED  # nosec
    short_nodeid = str(node_id)[:4]
    screenshots = []

    # Example https://github.com/Ybalrid/Ogre_glTF/raw/6a59adf2f04253a3afb9459549803ab297932e8d/Media/Monster.glb
    if "file-picker" in node.key and node.outputs is not None:
        try:
            user_id = request[RQT_USERID_KEY]
            assert node.outputs is not None  # nosec

            filelink = parse_obj_as(SimCoreFileLink, node.outputs["outFile"])

            file_url = await get_download_link(request.app, user_id, filelink)
            screenshots.append(
                NodeScreenshot(
                    thumbnail_url=f"https://placehold.co/170x120?text=render-{short_nodeid}",
                    file_url=file_url,
                )
            )
        except (KeyError, ValidationError) as err:
            _logger.debug("Failed to create link from file-picker: %s", err)
            pass

    elif node.key.startswith("simcore/services/dynamic"):
        # For dynamic services, just create fake images

        # References:
        # - https://github.com/Ybalrid/Ogre_glTF
        # - https://placehold.co/
        # - https://picsum.photos/
        #
        count = int(str(node_id.int)[0])

        screenshots = [
            NodeScreenshot(
                thumbnail_url=f"https://placehold.co/170x120?text=img-{short_nodeid}",
                file_url=f"https://picsum.photos/seed/{node_id.int + n}/500",
                mimetype="image/jpeg",
            )
            for n in range(count)
        ]

    return screenshots
