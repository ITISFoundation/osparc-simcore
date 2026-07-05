from celery import (  # type: ignore[import-untyped] # pylint: disable=no-name-in-module
    Task,
)
from celery_library.worker.app_server import get_app_server
from models_library.celery import TaskKey

from ....models.domain.chatbot import (
    ChatCompletionRequestMessage,
    CreateChatCompletionResponse,
    RoleEnum,
)
from ....models.schemas.responses import CreateResponseRequest
from ....services_http.chatbot import ChatbotApi


async def run_chat_completion(
    task: Task,
    task_key: TaskKey,
    *,
    request: CreateResponseRequest,
) -> CreateChatCompletionResponse:
    assert task_key  # nosec
    app = get_app_server(task.app).app

    chatbot_api = ChatbotApi.get_instance(app)
    assert isinstance(chatbot_api, ChatbotApi)  # nosec

    messages = [
        ChatCompletionRequestMessage(
            role=RoleEnum(msg.role),
            content=msg.content,
        )
        for msg in request.input
    ]

    return await chatbot_api.create_chat_completion(
        messages=messages,
        model=request.model,
        metadata=request.metadata or {},
        temperature=request.temperature,
    )
