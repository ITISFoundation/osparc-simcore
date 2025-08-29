import logging
import uuid
from functools import lru_cache

from aiohttp import web
from models_library.utils.pydantic_tools_extension import parse_obj_or_none
from pydantic import ByteSize
from servicelib.logging_utils import log_decorator

from ._errors import FileToLargeError, IncompatibleServiceError
from ._models import ViewerInfo
from ._repository import StudiesDispatcherRepository
from .settings import get_plugin_settings

_BASE_UUID = uuid.UUID("ca2144da-eabb-4daf-a1df-a3682050e25f")


_logger = logging.getLogger(__name__)


@lru_cache
def compose_uuid_from(*values) -> uuid.UUID:
    composition: str = "/".join(map(str, values))
    return uuid.uuid5(_BASE_UUID, composition)


async def list_viewers_info(
    app: web.Application, file_type: str | None = None, *, only_default: bool = False
) -> list[ViewerInfo]:
    repo = StudiesDispatcherRepository.create_from_app(app)
    return await repo.list_viewers_info(file_type=file_type, only_default=only_default)


async def get_default_viewer(
    app: web.Application,
    file_type: str,
    file_size: int | None = None,
) -> ViewerInfo:
    """

    Raises:
        IncompatibleService
        FileToLarge
    """
    repo = StudiesDispatcherRepository.create_from_app(app)
    viewer = await repo.get_default_viewer_for_filetype(file_type=file_type)

    if viewer is None:
        raise IncompatibleServiceError(file_type=file_type)

    if current_size := parse_obj_or_none(ByteSize, file_size):
        max_size: ByteSize = get_plugin_settings(app).STUDIES_MAX_FILE_SIZE_ALLOWED
        if current_size > max_size:
            raise FileToLargeError(file_size_in_mb=current_size.to("MiB"))

    return viewer


@log_decorator(_logger, level=logging.DEBUG)
async def validate_requested_viewer(
    app: web.Application,
    file_type: str,
    file_size: int | None = None,
    service_key: str | None = None,
    service_version: str | None = None,
) -> ViewerInfo:
    """

    Raises:
        IncompatibleService: When there is no match

    """
    if not service_key and not service_version:
        return await get_default_viewer(app, file_type, file_size)

    if service_key and service_version:
        repo = StudiesDispatcherRepository.create_from_app(app)
        viewer = await repo.find_compatible_viewer(
            file_type=file_type,
            service_key=service_key,
            service_version=service_version,
        )
        if viewer:
            return viewer

    raise IncompatibleServiceError(file_type=file_type)


@log_decorator(_logger, level=logging.DEBUG)
def validate_requested_file(
    app: web.Application, file_type: str, file_size: int | None = None
):
    # NOTE in the future we might want to prevent some types to be pulled
    assert file_type  # nosec

    if current_size := parse_obj_or_none(ByteSize, file_size):
        max_size: ByteSize = get_plugin_settings(app).STUDIES_MAX_FILE_SIZE_ALLOWED
        if current_size > max_size:
            raise FileToLargeError(file_size_in_mb=current_size.to("MiB"))
