from typing import Any, Final

from models_library.celery import (
    GroupExecutionMetadata,
    GroupTaskExecutionMetadata,
    GroupUUID,
    OwnerMetadata,
    TaskExecutionMetadata,
    TaskName,
    TaskUUID,
)

from ..task_manager import TaskManager

NOTIFICATIONS_SERVICE_QUEUE_NAME: Final[str] = "notifications"
SEND_MESSAGE_TASK_NAME_TEMPLATE: Final[TaskName] = "send_{}_message"


async def submit_send_message_task(
    task_manager: TaskManager,
    *,
    owner_metadata: OwnerMetadata,
    message: dict[str, Any],  # NOTE: validated internally
) -> tuple[TaskUUID, TaskName]:
    return await task_manager.submit_task(
        TaskExecutionMetadata(
            name=SEND_MESSAGE_TASK_NAME_TEMPLATE.format(message["channel"]),
            queue=NOTIFICATIONS_SERVICE_QUEUE_NAME,
        ),
        owner_metadata=owner_metadata,
        message=message,
    ), SEND_MESSAGE_TASK_NAME_TEMPLATE.format(message["channel"])


async def submit_send_messages_task(
    task_manager: TaskManager,
    *,
    owner_metadata: OwnerMetadata,
    messages: list[dict[str, Any]],  # NOTE: validated internally
) -> tuple[GroupUUID, list[TaskUUID], TaskName]:
    group_uuid, task_uuids = await task_manager.submit_group(
        GroupExecutionMetadata(
            name="send_messages",
            tasks=[
                (
                    GroupTaskExecutionMetadata(
                        name=SEND_MESSAGE_TASK_NAME_TEMPLATE.format(message["channel"]),
                        queue=NOTIFICATIONS_SERVICE_QUEUE_NAME,
                    ),
                    {"message": message},
                )
                for message in messages
            ],
        ),
        owner_metadata=owner_metadata,
    )
    return group_uuid, task_uuids, SEND_MESSAGE_TASK_NAME_TEMPLATE.format(messages[0]["channel"])
