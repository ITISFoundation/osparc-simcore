from celery import (  # type: ignore[import-untyped] # pylint: disable=no-name-in-module
    Task,
)
from celery_library.worker.app_server import get_app_server
from models_library.celery import TaskKey

from ....models.domain.chatbot import (
    CreateChatCompletionResponse,
)
from ....models.schemas.responses import CreateResponseRequest
from ....services_http.chatbot import ChatbotApi, ChatbotSession


async def run_chat_completion(
    task: Task,
    task_key: TaskKey,
    *,
    request: CreateResponseRequest,
) -> CreateChatCompletionResponse:
    assert task_key  # nosec
    app = get_app_server(task.app).app
    chatbot_settings = app.state.settings.API_SERVER_CHATBOT

    chatbot_api = ChatbotApi.get_instance(app)
    assert isinstance(chatbot_api, ChatbotApi)  # nosec
    chatbot_session = ChatbotSession(
        _chatbot_settings=chatbot_settings,
        _api=chatbot_api,
    )

    return await chatbot_session.create_chat_completion(
        messages=[msg.to_domain_model() for msg in request.input],
        model=request.model,
        metadata=request.metadata or {},
        temperature=request.temperature,
    )
