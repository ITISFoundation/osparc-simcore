# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
# pylint:disable=protected-access

from dataclasses import dataclass

import respx
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from simcore_service_datcore_adapter.utils.client_base import (
    BaseServiceClientApi,
    setup_client_instance,
)


async def test_setup_client_instance():
    @dataclass
    class TheClientApi(BaseServiceClientApi):
        x: int = 33

    # setup app
    app = FastAPI()
    assert not TheClientApi.get_instance(app)

    setup_client_instance(
        app,
        api_cls=TheClientApi,
        api_baseurl="http://the_service",
        service_name="the_service",
        health_check_path="/health",
        x=42,
    )
    assert not TheClientApi.get_instance(app)

    # test startup/shutdown
    async with LifespanManager(app):

        # check startup
        assert TheClientApi.get_instance(app)
        api_obj = TheClientApi.get_instance(app)

        # test responsivity
        assert await api_obj.is_responsive() == False

        # now start the server
        with respx.mock(
            base_url="http://the_service",
            assert_all_mocked=True,
        ) as respx_mock:
            respx_mock.get("/health", name="health_check").respond(
                200, content="healthy"
            )
            # test responsitivity
            assert await api_obj.is_responsive()
            assert respx_mock["health_check"].called

            assert respx_mock["health_check"].call_count == 1

    # check shutdown
    assert not TheClientApi.get_instance(app), "Expected automatically cleaned"
