from collections.abc import Callable

import pytest
import socketio
from aiohttp import web
from faker import Faker
from fastapi import FastAPI
from simcore_service_payments.services.socketio import emit_to_frontend
from socketio import AsyncAioPikaManager, AsyncServer


async def test_socketio_setup():
    # is this closing properly?
    ...


@pytest.fixture
async def socketio_aiohttp_server(aiohttp_server: Callable):
    aiohttp_app = web.Application()
    server = await aiohttp_server(aiohttp_app)

    # Emulates simcore_service_webserver/socketio/server.py
    server_manager = AsyncAioPikaManager(url=get_rabbitmq_settings(app).dsn)
    sio_server = AsyncServer(
        async_mode="aiohttp",
        engineio_logger=True,
        client_manager=server_manager,
    )
    sio_server.attach(aiohttp_app)


async def test_emit_socketio_event_to_front_end(app: FastAPI, faker: Faker, sio_server):
    # create a server

    # create a client
    async with socketio.AsyncSimpleClient(logger=True, engineio_logger=True) as sio:

        # connect to a server
        await sio.connect(server_url, transports=["websocket"])
        session_client_id = sio.sid

        # emit from external
        await emit_to_frontend(
            app, event_name="event", data={"foo": "bar"}, to=session_client_id
        )

        # client receives it
        event: list = await sio.receive(timeout=5)
        event_name, *event_kwargs = event

        assert event_name == "event"
