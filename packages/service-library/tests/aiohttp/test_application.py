import asyncio

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
    async def _other_on_startup(app: web.Application):
        fire_and_forget = asyncio.create_task(asyncio.sleep(100), name="startup")
        app[APP_FIRE_AND_FORGET_TASKS_KEY].add(fire_and_forget)

    async def _other_on_shutdown(_: web.Application):
        assert first_call_on_startup_spy.called
        # shutdow is before cleanup
        assert not first_call_on_cleanup_spy.called

        # What if I add one more background task here??
        fire_and_forget = asyncio.create_task(asyncio.sleep(100), name="shutdown")
        app[APP_FIRE_AND_FORGET_TASKS_KEY].add(fire_and_forget)

    async def _other_on_cleanup(_: web.Application):
        assert first_call_on_startup_spy.called
        assert first_call_on_cleanup_spy.called

        # What if I add one more background task here??
        # WARNING: uncommenting this line suggests that we cannot add f&f tasks on-cleanup callbacks !!!
        #  app[APP_FIRE_AND_FORGET_TASKS_KEY].add( asyncio.create_task(asyncio.sleep(100), name="cleanup") )

    async def _other_cleanup_context(app: web.Application):
        # context seem to start first
        assert not first_call_on_startup_spy.called
        assert not first_call_on_cleanup_spy.called
        assert persistent_client_session_spy.call_count == 1

        # What if I add one more background task here?? OK
        fire_and_forget = asyncio.create_task(asyncio.sleep(100), name="setup")
        app[APP_FIRE_AND_FORGET_TASKS_KEY].add(fire_and_forget)

        yield

        assert first_call_on_startup_spy.called
        assert not first_call_on_cleanup_spy.called
        assert persistent_client_session_spy.call_count == 1

        # What if I add one more background task here??
        fire_and_forget = asyncio.create_task(asyncio.sleep(100), name="teardown")
        app[APP_FIRE_AND_FORGET_TASKS_KEY].add(fire_and_forget)

    # setup
    app = servicelib.aiohttp.application.create_safe_application()

    assert len(app.on_startup) > 0
    assert len(app.on_cleanup) > 0
    assert len(app.cleanup_ctx) > 0

    # NOTE there are 4 type of different events
    app.on_startup.append(_other_on_startup)
    app.on_shutdown.append(_other_on_shutdown)
    app.on_cleanup.append(_other_on_cleanup)
    app.cleanup_ctx.append(_other_cleanup_context)

    # pre-start checks  -----------
    assert APP_CLIENT_SESSION_KEY not in app

    # starting -----------
    server = TestServer(app)
    await server.start_server()
    # started -----------

    assert first_call_on_startup_spy.call_count == 1
    assert first_call_on_cleanup_spy.call_count == 0
    assert persistent_client_session_spy.call_count == 1

    # persistent_client_session  created client
    assert APP_CLIENT_SESSION_KEY in app

    # stopping -----------
    await server.close()
    # stopped -----------

    assert first_call_on_startup_spy.call_count == 1
    assert first_call_on_cleanup_spy.call_count == 1
    assert persistent_client_session_spy.call_count == 1

    # persistent_client_session closed session
    assert app[APP_CLIENT_SESSION_KEY].closed

    # checks that _cancel_all_background_tasks worked?
    fire_and_forget_tasks = app[APP_FIRE_AND_FORGET_TASKS_KEY]
    done = [t for t in fire_and_forget_tasks if t.done()]
    cancelled = [t for t in fire_and_forget_tasks if t.cancelled]
    pending = [t for t in fire_and_forget_tasks if not t.cancelled() or not t.done()]
    assert not pending
    assert done or cancelled

    # will create a new client
    # WARNING: POTENTIAL BUG
    #  a client created in a cleanup event might leave client session opened!
    assert get_client_session(app).closed is False
