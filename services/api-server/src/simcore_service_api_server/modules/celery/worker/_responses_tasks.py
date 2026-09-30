import logging

from celery import (  # type: ignore[import-untyped] # pylint: disable=no-name-in-module
    Task,
)
from celery_library.worker.app_server import get_app_server
from models_library.celery import TaskKey

from ....clients.chatbot_usage import Reservation, UsageRecord, get_chatbot_usage_ledger
from ....models.domain.celery_models import ApiServerOwnerMetadata
from ....models.domain.chatbot import DEFAULT_TOP_P, CreateChatCompletionResponse
from ....models.schemas.responses import CreateResponseRequest
from ....services_http.chatbot import ChatbotApi, ChatbotSession

_logger = logging.getLogger(__name__)


async def run_chat_completion(
    task: Task,
    task_key: TaskKey,
    *,
    request: CreateResponseRequest,
    reservation_usd: float | None = None,
) -> CreateChatCompletionResponse:
    assert task_key  # nosec
    app = get_app_server(task.app).app
    chatbot_settings = app.state.settings.API_SERVER_CHATBOT

    ledger = get_chatbot_usage_ledger(app)
    reservation: Reservation | None = None
    if reservation_usd is not None:
        if ledger is None:
            # limits were disabled between submit and task start: the submit-time
            # Reservation ages out with the window TTL; keep it visible in logs
            _logger.error("Reservation placed but usage limits are disabled on the worker")
        else:
            # the worker re-checks the Global Budget Guard at task start (it may have
            # been hit while the job was queued) and debits at task end
            await ledger.ensure_global_budget_available()
            owner = ApiServerOwnerMetadata.model_validate_key(task_key)
            reservation = Reservation(
                user_id=owner.user_id,
                product_name=owner.product_name,
                amount_usd=reservation_usd,
            )

    chatbot_api = ChatbotApi.get_instance(app)
    assert isinstance(chatbot_api, ChatbotApi)  # nosec
    chatbot_session = ChatbotSession(
        _chatbot_settings=chatbot_settings,
        _api=chatbot_api,
    )

    try:
        completion = await chatbot_session.create_chat_completion(
            messages=[msg.to_domain_model() for msg in request.input],
            model=request.model,
            metadata=request.metadata or {},
            temperature=request.temperature,
            top_p=DEFAULT_TOP_P,
            response_format=request.to_chat_response_format(),
        )
    except BaseException:
        if reservation and ledger:
            await ledger.release(reservation, reason="task_failed")
        raise

    if reservation and ledger:
        await ledger.reconcile(reservation, _usage_from_completion(completion, request))

    return completion


def _usage_from_completion(
    completion: CreateChatCompletionResponse,
    request: CreateResponseRequest,
) -> UsageRecord:
    if completion.usage and completion.usage.total_tokens:
        return UsageRecord(
            total_tokens=completion.usage.total_tokens,
            prompt_tokens=completion.usage.prompt_tokens,
            completion_tokens=completion.usage.completion_tokens,
        )
    # missing usage: estimate from text length and never fail the completion over accounting
    input_chars = sum(len(msg.content) for msg in request.input)
    output_chars = len(completion.choices[0].message.content or "") if completion.choices else 0
    return UsageRecord.estimated_from_text(input_chars=input_chars, output_chars=output_chars)
