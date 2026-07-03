import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status

from ...exceptions.service_errors_utils import DEFAULT_BACKEND_SERVICE_STATUS_CODES
from ...models.schemas.errors import ErrorGet
from ...models.schemas.responses import CreateResponseRequest, ResponseObject
from ..dependencies.authentication import get_current_user_id
from ._constants import FMSG_CHANGELOG_NEW_IN_VERSION, OPENAI_COMPATIBLE_TAG, create_route_description

_logger = logging.getLogger(__name__)

router = APIRouter(tags=[OPENAI_COMPATIBLE_TAG])

_RESPONSES_STATUS_CODES: dict[int | str, dict[str, Any]] = {
    status.HTTP_404_NOT_FOUND: {
        "description": "Response not found",
        "model": ErrorGet,
    },
    **DEFAULT_BACKEND_SERVICE_STATUS_CODES,
}

_CANCEL_STATUS_CODES: dict[int | str, dict[str, Any]] = {
    **DEFAULT_BACKEND_SERVICE_STATUS_CODES,
}


@router.post(
    "",
    description=create_route_description(
        base="Creates a model response (OpenAI Responses API compatible)",
        changelog=[
            FMSG_CHANGELOG_NEW_IN_VERSION.format("0.13.2"),
        ],
    ),
    response_model=ResponseObject,
    responses=_RESPONSES_STATUS_CODES,
    status_code=status.HTTP_200_OK,
)
async def create_response(
    body: CreateResponseRequest,
    user_id: Annotated[int, Depends(get_current_user_id)],
) -> ResponseObject:
    msg = "Not implemented"
    raise NotImplementedError(msg)


@router.get(
    "/{response_id}",
    description=create_route_description(
        base=(
            "Retrieves a model response by ID. "
            "Use to poll status of background responses (OpenAI Responses API compatible)"
        ),
        changelog=[
            FMSG_CHANGELOG_NEW_IN_VERSION.format("0.13.2"),
        ],
    ),
    response_model=ResponseObject,
    responses=_RESPONSES_STATUS_CODES,
)
async def get_response(
    response_id: str,
    user_id: Annotated[int, Depends(get_current_user_id)],
) -> ResponseObject:
    msg = "Not implemented"
    raise NotImplementedError(msg)


@router.post(
    "/{response_id}/cancel",
    description=create_route_description(
        base="Cancels an in-progress background response (OpenAI Responses API compatible)",
        changelog=[
            FMSG_CHANGELOG_NEW_IN_VERSION.format("0.13.2"),
        ],
    ),
    response_model=ResponseObject,
    responses=_CANCEL_STATUS_CODES,
)
async def cancel_response(
    response_id: str,
    user_id: Annotated[int, Depends(get_current_user_id)],
) -> ResponseObject:
    msg = "Not implemented"
    raise NotImplementedError(msg)
