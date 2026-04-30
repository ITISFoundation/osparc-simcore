from typing import Any, Final

from models_library.celery import (
    GroupExecutionMetadata,
    GroupTaskExecutionMetadata,
    TaskExecutionMetadata,
    TaskID,
    TaskName,
)

from ..task_manager import TaskManager

NOTIFICATIONS_SERVICE_QUEUE_NAME: Final[str] = "notifications"
SEND_MESSAGE_TASK_NAME_TEMPLATE: Final[TaskName] = "send_{}_message"


async def submit_send_message_task(
    task_manager: TaskManager,
    *,
    owner: str,
    user_id: int | None = None,
    product_name: str | None = None,
    message: dict[str, Any],  # NOTE: validated internally
    description: str | None = None,
) -> tuple[TaskID, TaskName]:
    return await task_manager.submit_task(
        TaskExecutionMetadata(
            name=SEND_MESSAGE_TASK_NAME_TEMPLATE.format(message["channel"]),
            queue=NOTIFICATIONS_SERVICE_QUEUE_NAME,
            description=description,
        ),
        owner=owner,
        user_id=user_id,
        product_name=product_name,
        message=message,
    ), SEND_MESSAGE_TASK_NAME_TEMPLATE.format(message["channel"])


async def submit_send_messages_task(
    task_manager: TaskManager,
    *,
    owner: str,
    user_id: int | None = None,
    product_name: str | None = None,
    messages: list[dict[str, Any]],  # NOTE: validated internally
    description: str | None = None,
) -> tuple[TaskID, list[TaskID], TaskName]:
    group_id, task_ids = await task_manager.submit_group(
        GroupExecutionMetadata(
            name="send_messages",
            description=description,
            tasks=[
                (
                    GroupTaskExecutionMetadata(
                        name=SEND_MESSAGE_TASK_NAME_TEMPLATE.format(message["channel"]),
                        queue=NOTIFICATIONS_SERVICE_QUEUE_NAME,
                        description=description,
                    ),
                    {"message": message},
                )
                for message in messages
            ],
        ),
        owner=owner,
        user_id=user_id,
        product_name=product_name,
    )
    return group_id, task_ids, SEND_MESSAGE_TASK_NAME_TEMPLATE.format(messages[0]["channel"])
