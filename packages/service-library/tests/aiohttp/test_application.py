import asyncio

import servicelib.aiohttp.application
from aiohttp import web
from aiohttp.test_utils import TestServer
from pytest_mock import MockerFixture
from servicelib.aiohttp.application import (  # _first_call_on_shutdown,; _cancel_all_background_tasks,; _first_call_on_startup,
    create_safe_application,
)
from servicelib.aiohttp.client_session import APP_CLIENT_SESSION_KEY


async def _create_background_tasks(app: web.Application):
    app["background-tasks"]: list[asyncio.Task] = [
        asyncio.create_task(asyncio.sleep(100)) for i in range(5)
    ]


async def _other_shutdown(app: web.Application):
    ...


async def test_create_safe_application(mocker: MockerFixture):
    app = create_safe_application()

    # adds new
    app.on_startup.append(_create_background_tasks)

    # setup spies
    _first_call_on_startup_spy = mocker.spy(
        servicelib.aiohttp.application, "_first_call_on_startup"
    )
    _create_background_tasks_spy = mocker.spy(_create_background_tasks, "__call__")
    # _first_call_on_shutdown_spy = mocker.spy(_first_call_on_shutdown, "__call__")
    # _other_shutdown_spy = mocker.spy(_other_shutdown, "__call__")
    # _cancel_all_background_tasks_spy = mocker.spy(
    #    _cancel_all_background_tasks, "__call__"
    # )

    server = TestServer(app)

    # pre-start checks
    assert APP_CLIENT_SESSION_KEY not in app

    await server.start_server()
    # started

    assert _first_call_on_startup_spy.call_count == 1
    assert _create_background_tasks_spy.call_count == 1
    # assert not _first_call_on_shutdown_spy.called
    # assert not _other_shutdown_spy.called
    # assert not _cancel_all_background_tasks_spy.called

    # stopped
    await server.close()

    # post-stop checks

    assert _first_call_on_startup_spy.call_count == 1
    assert _create_background_tasks_spy.call_count == 1
    # assert _first_call_on_shutdown_spy.call_count == 1
    # assert _other_shutdown_spy.call_count == 1
    # assert _cancel_all_background_tasks_spy.call_count == 1

    assert all(task.closed for task in app["background-tasks"])

    # check order of events!
    _cancel_all_background_tasks_spy.call_args_list
