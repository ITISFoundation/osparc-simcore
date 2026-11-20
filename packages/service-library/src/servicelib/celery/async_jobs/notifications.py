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
from models_library.notifications import Channel
from models_library.products import ProductName

from ..task_manager import TaskManager

NOTIFICATIONS_QUEUE_PREFIX: Final[str] = "notifications"
SEND_MESSAGE_TASK_NAME_TEMPLATE: Final[TaskName] = "send_{}_message_task"


def notifications_queue_name(channel: Channel) -> str:
    """Per-channel queue so each channel worker can be scaled and rate-limited on its own"""
    return f"{NOTIFICATIONS_QUEUE_PREFIX}-{channel}"


def channel_from_notifications_queue_name(name: str) -> Channel:
    """Inverse of notifications_queue_name, for checking the queues a worker consumes"""
    prefix = f"{NOTIFICATIONS_QUEUE_PREFIX}-"
    if not name.startswith(prefix):
        msg = f"Queue '{name}' is not a notifications per-channel queue (expected '{prefix}<channel>')"
        raise ValueError(msg)
    return Channel(name.removeprefix(prefix))


async def submit_send_message_task(
    task_manager: TaskManager,
    *,
    owner_metadata: OwnerMetadata,
    product_name: ProductName,
    message: dict[str, Any],  # NOTE: validated internally
    description: str | None = None,
) -> tuple[TaskUUID, TaskName]:
    task_name = SEND_MESSAGE_TASK_NAME_TEMPLATE.format(message["channel"])
    return await task_manager.submit_task(
        TaskExecutionMetadata(
            name=task_name,
            queue=notifications_queue_name(Channel(message["channel"])),
            description=description,
        ),
        owner_metadata=owner_metadata,
        product_name=product_name,
        message=message,
    ), task_name


async def submit_send_messages_task(
    task_manager: TaskManager,
    *,
    owner_metadata: OwnerMetadata,
    product_name: ProductName,
    messages: list[dict[str, Any]],  # NOTE: validated internally
    description: str | None = None,
) -> tuple[GroupUUID, list[TaskUUID], TaskName]:
    group_uuid, task_uuids = await task_manager.submit_group(
        GroupExecutionMetadata(
            name="send_messages",
            description=description,
            tasks=[
                (
                    GroupTaskExecutionMetadata(
                        name=SEND_MESSAGE_TASK_NAME_TEMPLATE.format(message["channel"]),
                        queue=notifications_queue_name(Channel(message["channel"])),
                        description=description,
                    ),
                    {"product_name": product_name, "message": message},
                )
                for message in messages
            ],
        ),
        owner_metadata=owner_metadata,
    )
    return group_uuid, task_uuids, SEND_MESSAGE_TASK_NAME_TEMPLATE.format(messages[0]["channel"])
