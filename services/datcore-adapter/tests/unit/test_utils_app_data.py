# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from dataclasses import dataclass

from fastapi import FastAPI
from simcore_service_datcore_adapter.utils.app_data import AppDataMixin


@dataclass
class SomeAppData(AppDataMixin):
    x: int = 42


def test_create_once_appdata_instance():
    app = FastAPI()

    assert SomeAppData.get_instance(app) is None

    data = SomeAppData.create_once(app)
    assert isinstance(data, SomeAppData)

    # shall not create new instances within the same app
    assert SomeAppData.get_instance(app) is data
    assert SomeAppData.create_once(app) is data
    assert app.state.unique_someappdata is data

    # shall create a different instances with different apps
    app2 = FastAPI()
    assert SomeAppData.create_once(app2) == SomeAppData.create_once(app)
    assert SomeAppData.create_once(app2) is not SomeAppData.create_once(app)

    # used outside app context?
    data3 = SomeAppData()
    assert data3 == SomeAppData.get_instance(app)
    assert data3 is not SomeAppData.get_instance(app)
    assert data3 is not SomeAppData.get_instance(app2)


def test_pop_appdata_instance():
    app = FastAPI()

    data = SomeAppData.create_once(app)
    assert SomeAppData.pop_instance(app) is data

    assert SomeAppData.get_instance(app) is None
