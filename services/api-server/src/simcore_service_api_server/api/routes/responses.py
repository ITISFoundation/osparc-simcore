import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from models_library.products import ProductName
from models_library.users import UserID
from servicelib.celery.task_manager import TaskManager
from starlette.responses import JSONResponse

from simcore_service_api_server.models.domain.chatbot import CreateChatCompletionResponse

from ..._service_responses import (
    create_streaming_chat_response,
    submit_background_chat_response,
)
from ...clients.chatbox_usage import get_chatbox_usage_ledger
from ...core.settings import ApplicationSettings
from ...exceptions.backend_errors import ChatbotNotAvailableError
from ...exceptions.task_errors import TaskCancelledError, TaskError, TaskResultMissingError
from ...models.basic_types import SseStreamingResponse
from ...models.domain.celery_models import ApiServerOwnerMetadata
from ...models.schemas.errors import ErrorGet, UsageLimitErrorGet
from ...models.schemas.responses import (
    CreateResponseRequest,
    OutputMessage,
    OutputTextContent,
    ResponseObject,
    ResponseStatus,
    ResponseUsage,
)
from ...services_http.chatbot import ChatbotApi
from ...services_rpc.async_jobs import AsyncJobClient
from ..dependencies.application import get_settings
from ..dependencies.authentication import (
    get_credentials_hash,
    get_current_user_id,
    get_product_name,
)
from ..dependencies.celery import get_task_manager
from ..dependencies.services import get_api_client
from ..dependencies.tasks import get_async_jobs_client
from ._constants import (
    FMSG_CHANGELOG_ADDED_IN_VERSION,
    FMSG_CHANGELOG_NEW_IN_VERSION,
    OPENAI_COMPATIBLE_OPENAPI_EXTRA,
    create_route_description,
)

_logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "",
    description=create_route_description(
        base="Creates a model response (OpenAI Responses API compatible)",
        changelog=[
            FMSG_CHANGELOG_NEW_IN_VERSION.format("0.13.2"),
            FMSG_CHANGELOG_ADDED_IN_VERSION.format(
                "0.16.2",
                "`stream` field: when true, relays the answer as server-sent events instead of a background job",
            ),
        ],
    ),
    response_model=ResponseObject,
    status_code=status.HTTP_200_OK,
    responses={
        status.HTTP_403_FORBIDDEN: {
            "description": "The Chatbox Window Quota or the platform Provider Budget is exhausted",
            "model": UsageLimitErrorGet,
        },
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": "The request was rejected by the chatbot service",
            "model": ErrorGet,
        },
        status.HTTP_429_TOO_MANY_REQUESTS: {
            "description": "The per-API-key Chatbox rate limit was exceeded",
            "model": UsageLimitErrorGet,
        },
        status.HTTP_502_BAD_GATEWAY: {
            "description": "The chatbot service could not be reached or failed",
            "model": ErrorGet,
        },
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "The chatbot service is not reachable",
            "model": ErrorGet,
        },
    },
    openapi_extra=OPENAI_COMPATIBLE_OPENAPI_EXTRA,
)
async def create_response(
    request: Request,
    body: CreateResponseRequest,
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
    credentials_hash: Annotated[str, Depends(get_credentials_hash)],
    settings: Annotated[ApplicationSettings, Depends(get_settings)],
    task_manager: Annotated[TaskManager, Depends(get_task_manager)],
    chatbot_api: Annotated[ChatbotApi, Depends(get_api_client(ChatbotApi))],
) -> ResponseObject | SseStreamingResponse | JSONResponse:
    if settings.API_SERVER_CHATBOT is None:
        raise ChatbotNotAvailableError

    ledger = get_chatbox_usage_ledger(request.app)

    if body.stream:
        return await create_streaming_chat_response(
            chatbot_settings=settings.API_SERVER_CHATBOT,
            chatbot_api=chatbot_api,
            body=body,
            request=request,
            credentials_hash=credentials_hash,
            user_id=user_id,
            product_name=product_name,
            ledger=ledger,
        )

    return await submit_background_chat_response(
        task_manager=task_manager,
        body=body,
        credentials_hash=credentials_hash,
        user_id=user_id,
        product_name=product_name,
        ledger=ledger,
    )


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
    responses={
        status.HTTP_404_NOT_FOUND: {
            "description": "Response not found",
            "model": ErrorGet,
        },
    },
    openapi_extra=OPENAI_COMPATIBLE_OPENAPI_EXTRA,
)
async def get_response(
    response_id: str,
    user_id: Annotated[UserID, Depends(get_current_user_id)],
    product_name: Annotated[ProductName, Depends(get_product_name)],
    async_jobs_client: Annotated[AsyncJobClient, Depends(get_async_jobs_client)],
) -> ResponseObject:
    owner = ApiServerOwnerMetadata(user_id=user_id, product_name=product_name)
    job_id = UUID(response_id)

    job_status = await async_jobs_client.status(job_id=job_id, owner_metadata=owner)

    if not job_status.done:
        return ResponseObject(
            id=response_id,
            status=ResponseStatus.IN_PROGRESS,
        )

    try:
        result = await async_jobs_client.result(job_id=job_id, owner_metadata=owner)
    except TaskCancelledError:
        return ResponseObject(
            id=response_id,
            status=ResponseStatus.CANCELLED,
        )
    except (TaskError, TaskResultMissingError) as err:
        return ResponseObject(
            id=response_id,
            status=ResponseStatus.FAILED,
            error={"message": f"{err}"},
        )

    completion = CreateChatCompletionResponse.model_validate(result.result)
    output_text = ""
    if completion and completion.choices:
        output_text = completion.choices[0].message.content or ""

    return ResponseObject(
        id=response_id,
        status=ResponseStatus.COMPLETED,
        output=[
            OutputMessage(
                id=f"{response_id}-msg-0",
                status="completed",
                content=[OutputTextContent(text=output_text)],
            )
        ],
        usage=(
            ResponseUsage(
                prompt_tokens=completion.usage.prompt_tokens,
                completion_tokens=completion.usage.completion_tokens,
                total_tokens=completion.usage.total_tokens,
            )
            if completion and completion.usage
            else None
        ),
    )
