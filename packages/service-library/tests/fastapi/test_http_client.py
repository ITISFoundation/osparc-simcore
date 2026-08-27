# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import Iterator
from typing import ClassVar

import httpx
import pytest
import respx
from asgi_lifespan import LifespanManager
from fastapi import FastAPI, status
from fastapi_lifespan_manager import LifespanManager as AppLifespanManager
from models_library.healthchecks import IsResponsive
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from servicelib.fastapi.http_client import (
    AttachLifespanMixin,
    BaseHTTPApi,
    HealthMixinMixin,
)


def test_using_app_state_mixin():
    class SomeData(SingletonInAppStateMixin):
        app_state_name: ClassVar[str] = "my_data"
        frozen: bool = True

        def __init__(self, value):
            self.value = value

    # my app
    app = FastAPI()

    # load -> fails
    with pytest.raises(AttributeError):
        SomeData.get_from_app_state(app)

    # save
    obj = SomeData(42)
    obj.set_to_app_state(app)

    # load
    assert SomeData.get_from_app_state(app) == obj
    assert app.state.my_data == obj

    # cannot re-save if frozen
    assert SomeData.frozen
    with pytest.raises(ValueError, match=r"already in app\.state"):
        SomeData(32).set_to_app_state(app)

    # delete
    assert SomeData.pop_from_app_state(app) == obj
    with pytest.raises(AttributeError):
        SomeData.get_from_app_state(app)

    # save = load
    assert SomeData(32).set_to_app_state(app) == SomeData.get_from_app_state(app)


@pytest.fixture
def base_url() -> str:
    return "https://test_base_http_api"


@pytest.fixture
def mock_server_api(base_url: str) -> Iterator[respx.MockRouter]:
    with respx.mock(
        base_url=base_url,
        assert_all_called=False,
        assert_all_mocked=True,  # IMPORTANT: KEEP always True!
    ) as mock:
        mock.get("/").respond(status.HTTP_200_OK)
        yield mock


async def test_base_http_api(mock_server_api: respx.MockRouter, base_url: str):
    class MyClientApi(BaseHTTPApi, AttachLifespanMixin, HealthMixinMixin, SingletonInAppStateMixin):
        app_state_name: ClassVar[str] = "my_client_api"

    # create
    api = MyClientApi(client=httpx.AsyncClient(base_url=base_url))

    app_lifespan = AppLifespanManager[FastAPI]()
    api.attach_lifespan_to(app_lifespan)
    new_app = FastAPI(lifespan=app_lifespan)

    # or create from client kwargs
    assert MyClientApi.from_client_kwargs(base_url=base_url)

    # save to app.state
    api.set_to_app_state(new_app)
    assert MyClientApi.get_from_app_state(new_app) == api

    async with LifespanManager(
        new_app,
        startup_timeout=None,  # for debugging
        shutdown_timeout=10,
    ):
        # start event called
        assert not api.client.is_closed

        assert await api.ping()
        assert await api.is_healthy()

        alive = await api.check_liveness()
        assert bool(alive)
        assert isinstance(alive, IsResponsive)
        assert alive.elapsed.total_seconds() < 1

    # shutdown event
    assert api.client.is_closed


async def test_attach_lifespan_tears_down_after_setup_failure():
    events: list[str] = []

    class FailingClient(AttachLifespanMixin):
        async def setup_client(self) -> None:
            events.append("setup")
            msg = "setup failed"
            raise RuntimeError(msg)

        async def teardown_client(self) -> None:
            events.append("teardown")

    app_lifespan = AppLifespanManager[FastAPI]()
    FailingClient().attach_lifespan_to(app_lifespan)

    with pytest.raises(RuntimeError, match="setup failed"):
        async with LifespanManager(FastAPI(lifespan=app_lifespan)):
            pass

    assert events == ["setup", "teardown"]
