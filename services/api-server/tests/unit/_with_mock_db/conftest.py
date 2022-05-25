# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Iterator

import pytest
import pytest_simcore.helpers.catalog_data_fakers as catalog_data_fakers
import respx
from faker import Faker
from fastapi import FastAPI
from requests.auth import HTTPBasicAuth
from respx import MockRouter
from simcore_service_api_server.core.settings import ApplicationSettings


@pytest.fixture
def auth(mocker, app: FastAPI, faker: Faker) -> HTTPBasicAuth:
    # mock engine if db was not init
    if app.state.settings.API_SERVER_POSTGRES is None:

        engine = mocker.Mock()
        engine.minsize = 1
        engine.size = 10
        engine.freesize = 3
        engine.maxsize = 10
        app.state.engine = engine

    # patch authentication entry in repo
    faker_user_id = faker.pyint()

    # NOTE: here, instead of using the database, we patch repositories interface
    mocker.patch(
        "simcore_service_api_server.db.repositories.api_keys.ApiKeysRepository.get_user_id",
        return_value=faker_user_id,
    )
    mocker.patch(
        "simcore_service_api_server.db.repositories.users.UsersRepository.get_user_id",
        return_value=faker_user_id,
    )
    mocker.patch(
        "simcore_service_api_server.db.repositories.users.UsersRepository.get_email_from_user_id",
        return_value=faker.email(),
    )
    return HTTPBasicAuth(faker.word(), faker.password())


@pytest.fixture
def mocked_catalog_service_api(app: FastAPI) -> Iterator[MockRouter]:
    settings: ApplicationSettings = app.state.settings
    assert settings.API_SERVER_CATALOG

    # pylint: disable=not-context-manager
    with respx.mock(
        base_url=settings.API_SERVER_CATALOG.base_url,
        assert_all_called=False,
        assert_all_mocked=True,
    ) as respx_mock:

        respx_mock.get(
            "/services?user_id=1&details=false", name="list_services"
        ).respond(
            200,
            json=[
                # one solver
                catalog_data_fakers.create_service_out(
                    key="simcore/services/comp/Foo", name="Foo"
                ),
                # two version of the same solver
                catalog_data_fakers.create_service_out(version="0.0.1"),
                catalog_data_fakers.create_service_out(version="1.0.1"),
                # not a solver
                catalog_data_fakers.create_service_out(type="dynamic"),
            ],
        )

        yield respx_mock
