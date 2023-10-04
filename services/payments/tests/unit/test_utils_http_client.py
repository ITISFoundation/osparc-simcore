from collections.abc import Iterator

import httpx
import pytest
import respx
from asgi_lifespan import LifespanManager
from fastapi import FastAPI, status
from simcore_service_payments.utils.http_client import AppStateMixin, BaseHttpApi


def test_using_app_state_mixin():
    class SomeData(AppStateMixin):
        app_state_name: str = "my_data"
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
    with pytest.raises(ValueError):
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
    class MyClientApi(BaseHttpApi, AppStateMixin):
        app_state_name: str = "my_client_api"

    new_app = FastAPI()

    # create
    api = MyClientApi(client=httpx.AsyncClient(base_url=base_url))

    # or create from client kwargs
    assert MyClientApi.from_client_kwargs(base_url=base_url)

    # save to app.state
    api.set_to_app_state(new_app)
    assert MyClientApi.get_from_app_state(new_app) == api

    # defin lifespan
    api.attach_lifespan_to(new_app)

    async with LifespanManager(
        new_app,
        startup_timeout=None,  # for debugging
        shutdown_timeout=10,
    ):
        # start event called
        assert not api.client.is_closed

        assert await api.ping()
        assert await api.is_healhy()

    # shutdown event
    assert api.client.is_closed
