import logging
from typing import Optional

import sqlalchemy as sa
from aiohttp.web import Request, RouteTableDef
from servicelib.rest_utils import extract_and_validate
from simcore_service_storage.handlers import get_file_metadata

from .files_models import File, FileEdit
from .meta import api_version, api_version_prefix, app_name
from .models import file_meta_data

log = logging.getLogger(__name__)


routes = RouteTableDef()


class UserDrive:
    def __init__(self, user_id, engine):
        self.engine = engine

    # async def create_soft_link(
    #     file_id: str,
    #     new_file_id: str,
    # ) -> File:

    #     async with self.engine.acquire() as conn, conn.begin():

    #         stmt = file_meta_data.insert([])where(
    #             file_meta_data.c.file_uuid.startswith(prefix) & has_read_access
    #         )


@routes.post("/{file_id}:copy", name="copy_file")  # type: ignore
async def copy_file_handler(request: Request):

    # TODO: access rights?

    # TODO: validate request

    # TODO: transform into arguments and context
    user_id = request.query["user_id"]

    async def copy_file(
        file_id: str,
        as_soft_link: bool = False,
        new_file: Optional[FileEdit] = None,
    ) -> File:
        """ Creates a copy of a specified file """

        #
        # find file_id row
        # clone and
        # - rename file_uuid with new_file.id
        # - change time-stamp of creation
        # - inherits user_id

        print(file_id, as_soft_link, new_file)

        raise NotImplementedError()

    # copy: File = await copy_file(file_id, as_soft_link=, new_file=)

    # TODO: transform return into response
    # TODO: handler errors
