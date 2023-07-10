import asyncio

import pytest
import servicelib.aiohttp.application
from aiohttp import web
from aiohttp.test_utils import TestServer
from pytest_mock import MockerFixture
from servicelib.aiohttp.application_keys import APP_FIRE_AND_FORGET_TASKS_KEY
from servicelib.aiohttp.client_session import APP_CLIENT_SESSION_KEY, get_client_session


async def test_create_safe_application(mocker: MockerFixture):
    # setup spies before init
    first_call_on_startup_spy = mocker.spy(
        servicelib.aiohttp.application, "_first_call_on_startup"
    )
    first_call_on_cleanup_spy = mocker.spy(
        servicelib.aiohttp.application, "_first_call_on_cleanup"
    )
    persistent_client_session_spy = mocker.spy(
        servicelib.aiohttp.application, "persistent_client_session"
    )

    # some more events callbacks
    async def _other_on_startup(_app: web.Application):
        assert first_call_on_startup_spy.called
        assert not first_call_on_cleanup_spy.called
        assert persistent_client_session_spy.call_count == 1

        # What if I add one more background task here?? OK
        _app[APP_FIRE_AND_FORGET_TASKS_KEY].add(
            asyncio.create_task(asyncio.sleep(100), name="startup")
        )

    async def _other_on_shutdown(_app: web.Application):
        assert first_call_on_startup_spy.called
        assert not first_call_on_cleanup_spy.called

        # What if I add one more background task here?? OK
        _app[APP_FIRE_AND_FORGET_TASKS_KEY].add(
            asyncio.create_task(asyncio.sleep(100), name="shutdown")
        )

    async def _other_on_cleanup(_app: web.Application):
        assert first_call_on_startup_spy.called
        assert first_call_on_cleanup_spy.called

        # What if I add one more background task here?? NOT OK!!
        # WARNING: uncommenting this line suggests that we cannot add f&f tasks on-cleanup callbacks !!!
        # _app[APP_FIRE_AND_FORGET_TASKS_KEY].add( asyncio.create_task(asyncio.sleep(100), name="cleanup") )

    async def _other_cleanup_context(_app: web.Application):
        # context seem to start first
        assert not first_call_on_startup_spy.called
        assert not first_call_on_cleanup_spy.called
        assert persistent_client_session_spy.call_count == 1

        # What if I add one more background task here?? OK
        _app[APP_FIRE_AND_FORGET_TASKS_KEY].add(
            asyncio.create_task(asyncio.sleep(100), name="setup")
        )

        yield

        assert first_call_on_startup_spy.called
        assert not first_call_on_cleanup_spy.called
        assert persistent_client_session_spy.call_count == 1

        # What if I add one more background task here?? OK
        _app[APP_FIRE_AND_FORGET_TASKS_KEY].add(
            asyncio.create_task(asyncio.sleep(100), name="teardown")
        )

    # setup
    the_app = servicelib.aiohttp.application.create_safe_application()

    assert len(the_app.on_startup) > 0
    assert len(the_app.on_cleanup) > 0
    assert len(the_app.cleanup_ctx) > 0

    # NOTE there are 4 type of different events
    the_app.on_startup.append(_other_on_startup)
    the_app.on_shutdown.append(_other_on_shutdown)
    the_app.on_cleanup.append(_other_on_cleanup)
    the_app.cleanup_ctx.append(_other_cleanup_context)

    # pre-start checks  -----------
    assert APP_CLIENT_SESSION_KEY not in the_app

    # starting -----------
    server = TestServer(the_app)
    await server.start_server()
    # started -----------

    assert first_call_on_startup_spy.call_count == 1
    assert first_call_on_cleanup_spy.call_count == 0
    assert persistent_client_session_spy.call_count == 1

    # persistent_client_session  created client
    assert APP_CLIENT_SESSION_KEY in the_app

    # stopping -----------
    await server.close()
    # stopped -----------

    assert first_call_on_startup_spy.call_count == 1
    assert first_call_on_cleanup_spy.call_count == 1
    assert persistent_client_session_spy.call_count == 1

    # persistent_client_session closed session
    assert the_app[APP_CLIENT_SESSION_KEY].closed

    # checks that _cancel_all_background_tasks worked?
    fire_and_forget_tasks = the_app[APP_FIRE_AND_FORGET_TASKS_KEY]
    done = [t for t in fire_and_forget_tasks if t.done()]
    cancelled = [t for t in fire_and_forget_tasks if t.cancelled]
    pending = [t for t in fire_and_forget_tasks if not t.cancelled() or not t.done()]
    assert not pending
    assert done or cancelled

    # will create a new client
    # WARNING: POTENTIAL BUG a client created in a cleanup event might
    # leave client session opened!
    with pytest.raises(RuntimeError):
        get_client_session(the_app)


async def test_aiohttp_events_order():
    the_app = web.Application()
    the_app["events"] = []

    async def _on_startup(_app: web.Application):
        _app["events"].append("startup")

    async def _on_shutdown(_app: web.Application):
        _app["events"].append("shutdown")

    async def _on_cleanup(_app: web.Application):
        _app["events"].append("cleanup")

    async def _cleanup_context(_app: web.Application):
        _app["events"].append("cleanup_ctx.setup")
        yield
        _app["events"].append("cleanup_ctx.teardown")

    the_app.on_startup.append(_on_startup)
    the_app.on_shutdown.append(_on_shutdown)
    the_app.on_cleanup.append(_on_cleanup)
    the_app.cleanup_ctx.append(_cleanup_context)

    server = TestServer(the_app)
    await server.start_server()
    await server.close()

    # Events are triggered as follows
    # SEE https://docs.aiohttp.org/en/stable/web_advanced.html#aiohttp-web-signals
    #
    #  cleanup_ctx[0].setup   ---> begin of cleanup_ctx
    #  cleanup_ctx[1].setup.
    #      ...
    #  on_startup[0].
    #  on_startup[1].
    #      ...
    #  on_shutdown[0].
    #  on_shutdown[1].
    #      ...
    #  cleanup_ctx[1].teardown.
    #  cleanup_ctx[0].teardown <--- end of cleanup_ctx
    #  on_cleanup[0].
    #  on_cleanup[1].
    #      ...

    assert the_app["events"] == [
        "cleanup_ctx.setup",
        "startup",
        "shutdown",
        "cleanup_ctx.teardown",
        "cleanup",
    ]
