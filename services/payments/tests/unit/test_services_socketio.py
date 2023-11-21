from faker import Faker
from fastapi import FastAPI
from simcore_service_payments.services.socketio import emit_to_frontend


async def test_socketio_setup():
    # is this closing properly?
    ...


async def test_emit_socketio_event_to_front_end(app: FastAPI, faker: Faker):
    # create a client
    sid = faker.uuid4()

    # create a server

    # emit from external
    await emit_to_frontend(app, event_name="event", data={"foo": "bar"}, to=sid)

    # client receives it
