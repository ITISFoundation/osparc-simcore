# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name
from collections.abc import Iterator

import pytest
import sqlalchemy as sa
from pytest_mock import MockerFixture
from simcore_postgres_database.models.projects import projects
from simcore_postgres_database.models.workspaces import workspaces


@pytest.fixture
def workspaces_clean_db(postgres_db: sa.engine.Engine) -> Iterator[None]:
    with postgres_db.connect() as con:
        yield
        con.execute(workspaces.delete())
        con.execute(projects.delete())


@pytest.fixture
def mock_catalog_api_get_services_for_user_in_product(mocker: MockerFixture):
    mocker.patch(
        "simcore_service_webserver.projects._crud_api_read.catalog_service.get_services_for_user_in_product",
        spec=True,
        return_value=[],
    )
    mocker.patch(
        "simcore_service_webserver.projects._controller.projects_rest.are_project_services_available",
        spec=True,
        return_value=True,
    )
