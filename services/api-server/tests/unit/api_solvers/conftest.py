# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from typing import Iterator

import pytest
import respx
from fastapi import FastAPI
from pytest_simcore.helpers import catalog_data_fakers
from respx import MockRouter
from simcore_service_api_server.core.settings import ApplicationSettings


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
