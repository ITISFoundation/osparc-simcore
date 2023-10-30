import logging
from typing import Final

from fastapi import status
from httpx import AsyncClient, HTTPError
from models_library.api_schemas_directorv2.dynamic_services_service import (
    RunningDynamicServiceDetails,
)
from models_library.projects_nodes_io import NodeID
from pydantic import NonNegativeFloat, ValidationError

_logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT_S: Final[NonNegativeFloat] = 5


async def get_service_status(
    client: AsyncClient, node_id: NodeID
) -> RunningDynamicServiceDetails | None:
    try:
        response = await client.get(
            f"/dynamic_services/{node_id}", timeout=_REQUEST_TIMEOUT_S
        )
        if response.status_code != status.HTTP_200_OK:
            _logger.debug("")
            return None

        return RunningDynamicServiceDetails.parse_raw(response.text)
    except (ValidationError, HTTPError):
        _logger.debug("")
        return None


# TODO: add tests for this one
