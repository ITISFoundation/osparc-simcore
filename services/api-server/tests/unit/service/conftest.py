# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
from models_library.products import ProductName
from models_library.users import UserID
from pytest_mock import MockerFixture, MockType
from simcore_service_api_server._service_jobs import JobService
from simcore_service_api_server._service_solvers import SolverService
from simcore_service_api_server._service_studies import StudyService
from simcore_service_api_server.services_rpc.catalog import CatalogService
from simcore_service_api_server.services_rpc.wb_api_server import WbApiRpcClient


@pytest.fixture
def job_service(
    mocker: MockerFixture,
    mocked_webserver_rest_api_base: dict[str, MockType],
    mocked_webserver_rpc_api: dict[str, MockType],
    product_name: ProductName,
    user_id: UserID,
) -> JobService:
    return JobService(
        web_rest_api=mocker.MagicMock(),  # TODO: might want to return the real one
        web_rpc_api=WbApiRpcClient(_client=mocker.MagicMock()),
        user_id=user_id,
        product_name=product_name,
    )


@pytest.fixture
def catalog_service(
    mocker: MockerFixture,
    mocked_catalog_rpc_api: dict[str, MockType],
) -> CatalogService:
    return CatalogService(client=mocker.MagicMock())


@pytest.fixture
def solver_service(
    catalog_service: CatalogService,
    job_service: JobService,
) -> SolverService:
    return SolverService(catalog_service=catalog_service, job_service=job_service)


@pytest.fixture
def study_service(
    job_service: JobService,
) -> StudyService:

    return StudyService(job_service=job_service)
