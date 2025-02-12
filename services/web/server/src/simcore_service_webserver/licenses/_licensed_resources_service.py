# pylint: disable=unused-argument

import logging
from enum import Enum, auto
from pprint import pformat
from typing import NamedTuple

from aiohttp import web
from deepdiff import DeepDiff  # type: ignore[attr-defined]
from models_library.licenses import (
    LicensedResourceDB,
    LicensedResourceID,
    LicensedResourcePatchDB,
    LicensedResourceType,
)
from pydantic import BaseModel

from . import _licensed_resources_repository
from .errors import LicensedResourceNotFoundError

_logger = logging.getLogger(__name__)


class RegistrationState(Enum):
    ALREADY_REGISTERED = auto()
    DIFFERENT_RESOURCE = auto()
    NEWLY_REGISTERED = auto()


class RegistrationResult(NamedTuple):
    registered: LicensedResourceDB
    state: RegistrationState
    message: str | None


async def register_licensed_resource(
    app: web.Application,
    *,
    licensed_resource_name: str,
    licensed_resource_type: LicensedResourceType,
    licensed_resource_data: BaseModel,
    licensed_item_display_name: str,
) -> RegistrationResult:
    # NOTE about the implementation choice:
    # Using `create_if_not_exists` (INSERT with IGNORE_ON_CONFLICT) would have been an option,
    # but it generates excessive error logs due to conflicts.
    #
    # To avoid this, we first attempt to retrieve the resource using `get_by_resource_identifier` (GET).
    # If the resource does not exist, we proceed with `create_if_not_exists` (INSERT with IGNORE_ON_CONFLICT).
    #
    # This approach not only reduces unnecessary error logs but also helps prevent race conditions
    # when multiple concurrent calls attempt to register the same resource.

    resource_key = f"{licensed_resource_type}, {licensed_resource_name}"
    new_licensed_resource_data = licensed_resource_data.model_dump(
        mode="json",
        exclude_unset=True,
    )

    try:
        licensed_resource = (
            await _licensed_resources_repository.get_by_resource_identifier(
                app,
                licensed_resource_name=licensed_resource_name,
                licensed_resource_type=licensed_resource_type,
            )
        )

        if licensed_resource.licensed_resource_data != new_licensed_resource_data:
            ddiff = DeepDiff(
                licensed_resource.licensed_resource_data, new_licensed_resource_data
            )
            msg = (
                f"DIFFERENT_RESOURCE: {resource_key=} found in licensed_resource_id={licensed_resource.licensed_resource_id} with different data. "
                f"Diff:\n\t{pformat(ddiff, indent=2, width=200)}"
            )
            return RegistrationResult(
                licensed_resource, RegistrationState.DIFFERENT_RESOURCE, msg
            )

        return RegistrationResult(
            licensed_resource,
            RegistrationState.ALREADY_REGISTERED,
            f"ALREADY_REGISTERED: {resource_key=} found in licensed_resource_id={licensed_resource.licensed_resource_id}",
        )

    except LicensedResourceNotFoundError:
        licensed_resource = await _licensed_resources_repository.create_if_not_exists(
            app,
            display_name=licensed_item_display_name,
            licensed_resource_name=licensed_resource_name,
            licensed_resource_type=licensed_resource_type,
            licensed_resource_data=new_licensed_resource_data,
        )

        return RegistrationResult(
            licensed_resource,
            RegistrationState.NEWLY_REGISTERED,
            f"NEWLY_REGISTERED: {resource_key=} registered with licensed_resource_id={licensed_resource.licensed_resource_id}",
        )


async def trash_licensed_resource(
    app: web.Application,
    *,
    licensed_resource_id: LicensedResourceID,
) -> None:
    await _licensed_resources_repository.update(
        app,
        licensed_resource_id=licensed_resource_id,
        updates=LicensedResourcePatchDB(trash=True),
    )


async def untrash_licensed_resource(
    app: web.Application,
    *,
    licensed_resource_id: LicensedResourceID,
) -> None:
    await _licensed_resources_repository.update(
        app,
        licensed_resource_id=licensed_resource_id,
        updates=LicensedResourcePatchDB(trash=True),
    )
