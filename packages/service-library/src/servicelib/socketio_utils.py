"""Common utilities for python-socketio library


NOTE: we intentionally avoided importing socketio here to avoid adding an extra dependency at
this level which would include python-socketio in all libraries
"""

import asyncio


async def cleanup_socketio_async_pubsub_manager(server_manager):
    # NOTE: this is ugly. It seems though that python-socketio does not
    # cleanup its background tasks properly.
    # https://github.com/miguelgrinberg/python-socketio/discussions/1092
    cancelled_tasks = []

    if hasattr(server_manager, "thread"):
        server_thread = server_manager.thread
        assert isinstance(server_thread, asyncio.Task)  # nosec
        server_thread.cancel()
        cancelled_tasks.append(server_thread)

    if server_manager.publisher_channel:
        await server_manager.publisher_channel.close()

    if server_manager.publisher_connection:
        await server_manager.publisher_connection.close()

    current_tasks = asyncio.tasks.all_tasks()
    for task in current_tasks:
        coro = task.get_coro()
        if any(
            coro_name in coro.__qualname__  # type: ignore
            for coro_name in [
                "AsyncServer._service_task",
                "AsyncSocket.schedule_ping",
                "AsyncSocket._send_ping",
                "AsyncPubSubManager._thread",
            ]
        ):
            task.cancel()
            cancelled_tasks.append(task)
    await asyncio.gather(*cancelled_tasks, return_exceptions=True)
