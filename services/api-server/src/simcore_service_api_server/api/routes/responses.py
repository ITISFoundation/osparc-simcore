import logging
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

import httpx
from celery_library.async_jobs import submit_job
from fastapi import APIRouter, Depends, FastAPI, Request, status
from models_library.api_server.celery import API_SERVER_CELERY_QUEUE_DEFAULT
from models_library.celery import TaskExecutionMetadata
from models_library.products import ProductName
from models_library.users import UserID
from servicelib.celery.task_manager import TaskManager

from simcore_service_api_server.models.domain.chatbot import CreateChatCompletionResponse

from ...core.settings import ApplicationSettings
from ...exceptions.backend_errors import BaseBackEndError, ChatbotNotAvailableError
from ...exceptions.task_errors import TaskCancelledError, TaskError, TaskResultMissingError
from ...models.basic_types import SseStreamingResponse
from ...models.domain.celery_models import ApiServerOwnerMetadata
from ...models.schemas.errors import ErrorGet
from ...models.schemas.responses import (
    CreateResponseRequest,
    OutputMessage,
    OutputTextContent,
    ResponseObject,
    ResponseStatus,
)
from ...services_http.chatbot import ChatbotApi, ChatbotSession
from ...services_rpc.async_jobs import AsyncJobClient
from ..dependencies.application import get_app, get_settings
from ..dependencies.authentication import get_current_user_id, get_product_name
from ..dependencies.celery import get_task_manager
from ..dependencies.tasks import get_async_jobs_client
from ._constants import (
    FMSG_CHANGELOG_ADDED_IN_VERSION,
    FMSG_CHANGELOG_NEW_IN_VERSION,
    OPENAI_COMPATIBLE_OPENAPI_EXTRA,
    create_route_description,
)

_logger = logging.getLogger(__name__)

router = APIRouter()

_TASK_NAME = "run_chat_completion"


async def _relay_sse_response(response: httpx.Response, request: Request) -> AsyncIterator[bytes]:
    try:
        async for chunk in response.aiter_bytes():
            if await request.is_disconnected():
                break
            yield chunk
    finally:
        await response.aclose()


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
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Chatbot service is not enabled",
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
    settings: Annotated[ApplicationSettings, Depends(get_settings)],
    task_manager: Annotated[TaskManager, Depends(get_task_manager)],
    app: Annotated[FastAPI, Depends(get_app)],
) -> ResponseObject | SseStreamingResponse:
    if settings.API_SERVER_CHATBOT is None:
        raise ChatbotNotAvailableError

    if body.stream:
        chatbot_api = ChatbotApi.get_instance(app)
        assert isinstance(chatbot_api, ChatbotApi)  # nosec
        chatbot_session = ChatbotSession(
            _chatbot_settings=settings.API_SERVER_CHATBOT,
            _api=chatbot_api,
        )
        try:
            upstream_response = await chatbot_session.stream_chat_completion(
                messages=[msg.to_domain_model() for msg in body.input],
                model=body.model,
                metadata=body.metadata or {},
                temperature=body.temperature,
                response_format=body.to_chat_response_format(),
            )
        except httpx.HTTPError as exc:
            raise BaseBackEndError from exc
        return SseStreamingResponse(_relay_sse_response(upstream_response, request))

    job = await submit_job(
        task_manager,
        execution_metadata=TaskExecutionMetadata(
            name=_TASK_NAME,
            queue=API_SERVER_CELERY_QUEUE_DEFAULT,
        ),
        owner_metadata=ApiServerOwnerMetadata(user_id=user_id, product_name=product_name),
        request=body,
    )
    return ResponseObject(
        id=f"{job.job_id}",
        background=True,
        model=body.model,
        status=ResponseStatus.QUEUED,
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
    )
