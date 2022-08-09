"""
Showcases/tests an example of long running tasks.

How these tests works:
- setup a FastAPI server and launch it in the background.
- client directly makes requests to the FastAPI background client.

"""

# pylint: disable=redefined-outer-name

import asyncio
import sys
from pathlib import Path
from typing import Callable, Final

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient
from pydantic import PositiveFloat

# TESTS
from pytest_simcore.helpers.utils_assert import assert_status
from servicelib.aiohttp import long_running_tasks
from servicelib.json_serialization import json_dumps
from tenacity._asyncio import AsyncRetrying
from tenacity.retry import retry_if_exception_type
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_fixed

CURRENT_FILE = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve()
CURRENT_DIR = CURRENT_FILE.parent

ITEM_PUBLISH_SLEEP: Final[float] = 0.1

# UTILS


# def create_mock_app() -> FastAPI:
#     mock_server_app = FastAPI(title="app containing the server")

#     long_running_tasks.server.setup(mock_server_app)

#     @mock_server_app.get("/")
#     def health() -> None:
#         """used to check if application is ready"""

#     @mock_server_app.post("/string-list-task", status_code=status.HTTP_202_ACCEPTED)
#     async def create_string_list_task(
#         task_manager: long_running_tasks.server.TaskManager = Depends(
#             long_running_tasks.server.get_task_manager
#         ),
#     ) -> long_running_tasks.server.TaskId:
#         async def _string_list_task(
#             task_progress: long_running_tasks.server.TaskProgress, items: int
#         ) -> list[str]:
#             task_progress.publish(message="starting", percent=0)
#             generated_strings = []
#             for x in range(items):
#                 string = f"{x}"
#                 generated_strings.append(string)
#                 percent = x / items
#                 await asyncio.sleep(ITEM_PUBLISH_SLEEP)
#                 task_progress.publish(message="generated item", percent=percent)
#             task_progress.publish(message="finished", percent=1)
#             return generated_strings

#         # NOTE: TaskProgress is injected by start_task
#         task_id = long_running_tasks.server.start_task(
#             task_manager=task_manager, handler=_string_list_task, items=10
#         )
#         return task_id

#     @mock_server_app.post("/waiting-task", status_code=status.HTTP_202_ACCEPTED)
#     async def create_waiting_task(
#         wait_for: float,
#         task_manager: long_running_tasks.server.TaskManager = Depends(
#             long_running_tasks.server.get_task_manager
#         ),
#     ) -> long_running_tasks.server.TaskId:
#         async def _waiting_task(
#             task_progress: long_running_tasks.server.TaskProgress,
#             wait_for: PositiveFloat,
#         ) -> float:
#             task_progress.publish(message="started sleeping", percent=0.0)
#             await asyncio.sleep(wait_for)
#             task_progress.publish(message="finished sleeping", percent=1.0)
#             return 42 + wait_for

#         task_id = long_running_tasks.server.start_task(
#             task_manager=task_manager,
#             handler=_waiting_task,
#             wait_for=wait_for,
#         )
#         return task_id

#     return mock_server_app


@pytest.fixture
def high_status_poll_interval() -> PositiveFloat:
    # NOTE: polling very fast to capture all the progress updates and to check
    # that duplicate progress messages do not get sent
    return ITEM_PUBLISH_SLEEP / 5


@pytest.fixture
def app() -> web.Application:
    app = web.Application()
    routes = web.RouteTableDef()

    @routes.post("/long_running_task:start")
    async def generate_list_strings(request: web.Request):
        task_manager = long_running_tasks.server.get_task_manager(request.app)
        assert task_manager, "task manager is not initiated!"

        async def _string_list_task(
            task_progress: long_running_tasks.server.TaskProgress, num_strings: int
        ) -> list[str]:
            task_progress.publish(message="starting", percent=0)
            generated_strings = []
            for index in range(num_strings):
                generated_strings.append(f"{index}")
                await asyncio.sleep(ITEM_PUBLISH_SLEEP)
                task_progress.publish(
                    message="generated item", percent=index / num_strings
                )
            task_progress.publish(message="finished", percent=1)
            return generated_strings

        task_id = long_running_tasks.server.start_task(
            task_manager, _string_list_task, num_strings=10
        )
        return web.json_response(
            data={"data": task_id},
            status=web.HTTPAccepted.status_code,
            dumps=json_dumps,
        )

    app.add_routes(routes)
    long_running_tasks.server.setup(app)

    return app


@pytest.fixture
def client(
    event_loop: asyncio.AbstractEventLoop,
    aiohttp_client: Callable,
    unused_tcp_port_factory: Callable,
    app: web.Application,
) -> TestClient:

    return event_loop.run_until_complete(
        aiohttp_client(app, server_kwargs={"port": unused_tcp_port_factory()})
    )


async def test_workflow(
    client: TestClient,
    high_status_poll_interval: PositiveFloat,
) -> None:
    result = await client.post(f"/long_running_task:start")
    data, error = await assert_status(result, web.HTTPAccepted)
    task_id = data

    # get progress updates
    async for attempt in AsyncRetrying(
        wait=wait_fixed(0.1),
        stop=stop_after_delay(60),
        reraise=True,
        retry=retry_if_exception_type(AssertionError),
    ):
        with attempt:
            result = await client.get(f"{task_id}")
            data, error = await assert_status(result, web.HTTPOk)
            task_status = long_running_tasks.server.TaskStatus.parse_obj(data)
            assert task_status
            assert task_status.done, "task incomplete"

    import pdb

    pdb.set_trace()
    # progress_updates = []

    # async def progress_handler(
    #     message: long_running_tasks.client.ProgressMessage,
    #     percent: long_running_tasks.client.ProgressPercent,
    #     _: long_running_tasks.client.TaskId,
    # ) -> None:
    #     progress_updates.append((message, percent))

    # client = long_running_tasks.client.Client(
    #     app=client_app, async_client=async_client, base_url=run_server
    # )
    # async with long_running_tasks.client.periodic_task_result(
    #     client,
    #     task_id,
    #     task_timeout=10,
    #     progress_callback=progress_handler,
    #     status_poll_interval=high_status_poll_interval,
    # ) as result:
    #     string_list = result
    #     assert string_list == [f"{x}" for x in range(10)]

    #     assert progress_updates == [
    #         ("starting", 0.0),
    #         ("generated item", 0.0),
    #         ("generated item", 0.1),
    #         ("generated item", 0.2),
    #         ("generated item", 0.3),
    #         ("generated item", 0.4),
    #         ("generated item", 0.5),
    #         ("generated item", 0.6),
    #         ("generated item", 0.7),
    #         ("generated item", 0.8),
    #         ("finished", 1.0),
    #     ]


# async def test_error_after_result(
#     run_server: AnyHttpUrl,
#     client_app: FastAPI,
#     async_client: AsyncClient,
#     high_status_poll_interval: PositiveFloat,
# ) -> None:
#     result = await async_client.post(f"{run_server}/string-list-task")
#     assert result.status_code == status.HTTP_202_ACCEPTED
#     task_id = result.json()

#     client = long_running_tasks.client.Client(
#         app=client_app, async_client=async_client, base_url=run_server
#     )
#     with pytest.raises(RuntimeError):
#         async with long_running_tasks.client.periodic_task_result(
#             client,
#             task_id,
#             task_timeout=10,
#             status_poll_interval=high_status_poll_interval,
#         ) as result:
#             string_list = result
#             assert string_list == [f"{x}" for x in range(10)]
#             raise RuntimeError("has no influence")
