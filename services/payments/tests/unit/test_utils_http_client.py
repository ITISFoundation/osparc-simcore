import httpx
import pytest
from fastapi import FastAPI
from pydantic import BaseModel, HttpUrl
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
        SomeData.load_from_state(app)

    # save
    obj = SomeData(42)
    obj.save_to_state(app)

    # load
    assert SomeData.load_from_state(app) == obj
    assert app.state.my_data == obj

    # cannot re-save if frozen
    assert SomeData.frozen
    with pytest.raises(ValueError):
        SomeData(32).save_to_state(app)

    # delete
    assert SomeData.delete_from_state(app) == obj
    with pytest.raises(AttributeError):
        SomeData.load_from_state(app)

    # save = load
    assert SomeData(32).save_to_state(app) == SomeData.load_from_state(app)


@pytest.mark.skip()
def test_base_http_api():
    class MyAppSettings(BaseModel):
        MY_BASE_URL: HttpUrl = "https://test_base_http_api"

    class MyClientApi(BaseHttpApi, AppStateMixin):
        app_state_name: str = "my_client_api"
        raise_if_undefined: bool = True

    # my app
    app = FastAPI()
    app.state.settings = MyAppSettings()

    api = MyClientApi(client=httpx.AsyncClient(base_url="https://test_base_http_api"))
    api.save_to_state(app)

    assert MyClientApi.load_from_state(app) == api
