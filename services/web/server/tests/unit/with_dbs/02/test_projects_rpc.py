# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments


from collections.abc import AsyncIterator, Awaitable, Callable
from uuid import UUID

import pytest
from aiohttp.test_utils import TestClient
from common_library.users_enums import UserRole
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.rest_pagination import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    PageLimitInt,
    PageOffsetInt,
)
from models_library.rpc.webserver.projects import (
    ListProjectsMarkedAsJobRpcFilters,
    MetadataFilterItem,
    PageRpcProjectJobRpcGet,
    ProjectJobRpcGet,
)
from models_library.users import UserID
from pydantic import ValidationError
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from pytest_simcore.helpers.webserver_users import NewUser, UserInfoDict
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.webserver import projects as projects_rpc
from servicelib.rabbitmq.rpc_interfaces.webserver.errors import (
    ProjectForbiddenRpcError,
    ProjectNotFoundRpcError,
)
from servicelib.rabbitmq.rpc_interfaces.webserver.v1 import WebServerRpcClient
from settings_library.rabbit import RabbitSettings
from simcore_service_webserver.application_settings import ApplicationSettings
from simcore_service_webserver.projects.models import ProjectDict

pytest_simcore_core_services_selection = [
    "rabbit",
]


@pytest.fixture
def user_role() -> UserRole:
    # for logged_user
    return UserRole.USER


@pytest.fixture
def app_environment(
    rabbit_service: RabbitSettings,
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
):
    new_envs = setenvs_from_dict(
        monkeypatch,
        {
            **app_environment,
            "RABBIT_HOST": rabbit_service.RABBIT_HOST,
            "RABBIT_PORT": f"{rabbit_service.RABBIT_PORT}",
            "RABBIT_USER": rabbit_service.RABBIT_USER,
            "RABBIT_SECURE": f"{rabbit_service.RABBIT_SECURE}",
            "RABBIT_PASSWORD": rabbit_service.RABBIT_PASSWORD.get_secret_value(),
        },
    )

    settings = ApplicationSettings.create_from_envs()
    assert settings.WEBSERVER_RABBITMQ

    return new_envs


@pytest.fixture
async def rpc_client(
    rabbitmq_rpc_client: Callable[[str], Awaitable[RabbitMQRPCClient]],
) -> RabbitMQRPCClient:
    return await rabbitmq_rpc_client("client")


async def test_rpc_client_mark_project_as_job(
    rpc_client: RabbitMQRPCClient,
    product_name: ProductName,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
):
    # `logged_user` OWNS the `user_project` but not `other_user`
    project_uuid: ProjectID = UUID(user_project["uuid"])
    user_id = logged_user["id"]

    await projects_rpc.mark_project_as_job(
        rpc_client=rpc_client,
        product_name=product_name,
        user_id=user_id,
        project_uuid=project_uuid,
        job_parent_resource_name="solvers/solver123/version/1.2.3",
        storage_assets_deleted=False,
    )


@pytest.fixture(params=["free_functions", "v1_client"])
async def projects_interface(
    request: pytest.FixtureRequest,
    rpc_client: RabbitMQRPCClient,
):
    """Fixture that provides both free function and v1 client interfaces for projects."""
    if request.param == "free_functions":
        # Return a namespace object that mimics the free function interface
        class FreeFunction:
            @staticmethod
            async def list_projects_marked_as_jobs(
                rpc_client: RabbitMQRPCClient,
                *,
                product_name: ProductName,
                user_id: UserID,
                offset: PageOffsetInt = 0,
                limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
                filters: ListProjectsMarkedAsJobRpcFilters | None = None,
            ) -> PageRpcProjectJobRpcGet:
                return await projects_rpc.list_projects_marked_as_jobs(
                    rpc_client=rpc_client,
                    product_name=product_name,
                    user_id=user_id,
                    offset=offset,
                    limit=limit,
                    filters=filters,
                )

            @staticmethod
            async def mark_project_as_job(
                rpc_client: RabbitMQRPCClient,
                *,
                product_name: ProductName,
                user_id: UserID,
                project_uuid: ProjectID,
                job_parent_resource_name: str,
                storage_assets_deleted: bool,
            ) -> None:
                return await projects_rpc.mark_project_as_job(
                    rpc_client=rpc_client,
                    product_name=product_name,
                    user_id=user_id,
                    project_uuid=project_uuid,
                    job_parent_resource_name=job_parent_resource_name,
                    storage_assets_deleted=storage_assets_deleted,
                )

            @staticmethod
            async def get_project_marked_as_job(
                rpc_client: RabbitMQRPCClient,
                *,
                product_name: ProductName,
                user_id: UserID,
                project_uuid: ProjectID,
                job_parent_resource_name: str,
            ) -> ProjectJobRpcGet:
                return await projects_rpc.get_project_marked_as_job(
                    rpc_client=rpc_client,
                    product_name=product_name,
                    user_id=user_id,
                    project_uuid=project_uuid,
                    job_parent_resource_name=job_parent_resource_name,
                )

        return FreeFunction(), rpc_client

    assert request.param == "v1_client"
    # Return the v1 client interface
    v1_client = WebServerRpcClient(rpc_client)

    class V1ClientAdapter:
        def __init__(self, client: WebServerRpcClient):
            self._client = client

        async def list_projects_marked_as_jobs(
            self,
            rpc_client: RabbitMQRPCClient,  # Not used in v1, kept for compatibility
            *,
            product_name: ProductName,
            user_id: UserID,
            offset: PageOffsetInt = 0,
            limit: PageLimitInt = DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
            filters: ListProjectsMarkedAsJobRpcFilters | None = None,
        ) -> PageRpcProjectJobRpcGet:
            return await self._client.projects.list_projects_marked_as_jobs(
                product_name=product_name,
                user_id=user_id,
                offset=offset,
                limit=limit,
                filters=filters,
            )

        async def mark_project_as_job(
            self,
            rpc_client: RabbitMQRPCClient,  # Not used in v1, kept for compatibility
            *,
            product_name: ProductName,
            user_id: UserID,
            project_uuid: ProjectID,
            job_parent_resource_name: str,
            storage_assets_deleted: bool,
        ) -> None:
            return await self._client.projects.mark_project_as_job(
                product_name=product_name,
                user_id=user_id,
                project_uuid=project_uuid,
                job_parent_resource_name=job_parent_resource_name,
                storage_assets_deleted=storage_assets_deleted,
            )

        async def get_project_marked_as_job(
            self,
            rpc_client: RabbitMQRPCClient,  # Not used in v1, kept for compatibility
            *,
            product_name: ProductName,
            user_id: UserID,
            project_uuid: ProjectID,
            job_parent_resource_name: str,
        ) -> ProjectJobRpcGet:
            return await self._client.projects.get_project_marked_as_job(
                product_name=product_name,
                user_id=user_id,
                project_uuid=project_uuid,
                job_parent_resource_name=job_parent_resource_name,
            )

    return V1ClientAdapter(v1_client), rpc_client


async def test_rpc_client_list_my_projects_marked_as_jobs(
    projects_interface: tuple,
    product_name: ProductName,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
):
    interface, rpc_client = projects_interface
    project_uuid = ProjectID(user_project["uuid"])
    user_id = logged_user["id"]

    # Mark the project as a job first
    await interface.mark_project_as_job(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        project_uuid=project_uuid,
        job_parent_resource_name="solvers/solver123/version/1.2.3",
        storage_assets_deleted=False,
    )

    # List projects marked as jobs
    page: PageRpcProjectJobRpcGet = await interface.list_projects_marked_as_jobs(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        filters=ListProjectsMarkedAsJobRpcFilters(
            job_parent_resource_name_prefix="solvers/solver123"
        ),
    )

    assert page.meta.total == 1
    assert page.meta.offset == 0
    assert isinstance(page.data[0], ProjectJobRpcGet)

    project_job = page.data[0]
    assert project_job.uuid == project_uuid
    assert project_job.name == user_project["name"]
    assert project_job.description == user_project["description"]

    assert set(project_job.workbench.keys()) == set(user_project["workbench"].keys())


@pytest.fixture
async def other_user(
    client: TestClient,
    logged_user: UserInfoDict,
) -> AsyncIterator[UserInfoDict]:

    async with NewUser(
        user_data={
            "name": "other-user",
            "email": "other-user" + logged_user["email"],
        },
        app=client.app,
    ) as other_user_info:

        assert other_user_info["name"] != logged_user["name"]
        yield other_user_info


async def test_errors_on_rpc_client_mark_project_as_job(
    rpc_client: RabbitMQRPCClient,
    product_name: ProductName,
    logged_user: UserInfoDict,
    other_user: UserInfoDict,
    user_project: ProjectDict,
):
    # `logged_user` OWNS the `user_project` but not `other_user`
    project_uuid: ProjectID = UUID(user_project["uuid"])
    user_id = logged_user["id"]
    other_user_id = other_user["id"]

    with pytest.raises(ProjectForbiddenRpcError) as exc_info:
        await projects_rpc.mark_project_as_job(
            rpc_client=rpc_client,
            product_name=product_name,
            user_id=other_user_id,  # <-- no access
            project_uuid=project_uuid,
            job_parent_resource_name="solvers/solver123/version/1.2.3",
            storage_assets_deleted=False,
        )

    assert exc_info.value.error_context()["project_uuid"] == project_uuid

    with pytest.raises(ProjectNotFoundRpcError, match="not found"):
        await projects_rpc.mark_project_as_job(
            rpc_client=rpc_client,
            product_name=product_name,
            user_id=logged_user["id"],
            project_uuid=UUID("00000000-0000-0000-0000-000000000000"),  # <-- wont find
            job_parent_resource_name="solvers/solver123/version/1.2.3",
            storage_assets_deleted=False,
        )

    with pytest.raises(ValidationError, match="job_parent_resource_name") as exc_info:
        await projects_rpc.mark_project_as_job(
            rpc_client=rpc_client,
            product_name=product_name,
            user_id=user_id,
            project_uuid=project_uuid,
            job_parent_resource_name="This is not a resource",  # <-- wrong format
            storage_assets_deleted=False,
        )

    assert exc_info.value.error_count() == 1
    assert exc_info.value.errors()[0]["loc"] == ("job_parent_resource_name",)
    assert exc_info.value.errors()[0]["type"] == "value_error"


async def test_rpc_client_list_projects_marked_as_jobs_with_metadata_filter(
    rpc_client: RabbitMQRPCClient,
    product_name: ProductName,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
    client: TestClient,
):
    from simcore_service_webserver.projects import _metadata_service

    project_uuid = ProjectID(user_project["uuid"])
    user_id = logged_user["id"]

    # Mark the project as a job
    await projects_rpc.mark_project_as_job(
        rpc_client=rpc_client,
        product_name=product_name,
        user_id=user_id,
        project_uuid=project_uuid,
        job_parent_resource_name="solvers/solver123/version/1.2.3",
        storage_assets_deleted=False,
    )

    # Set custom metadata on the project
    custom_metadata = {
        "solver_type": "FEM",
        "mesh_cells": "10000",
        "domain": "biomedical",
    }

    await _metadata_service.set_project_custom_metadata(
        app=client.app,
        user_id=user_id,
        project_uuid=project_uuid,
        value=custom_metadata,
    )

    # Test with exact match on metadata field
    page: PageRpcProjectJobRpcGet = await projects_rpc.list_projects_marked_as_jobs(
        rpc_client=rpc_client,
        product_name=product_name,
        user_id=user_id,
        filters=ListProjectsMarkedAsJobRpcFilters(
            job_parent_resource_name_prefix="solvers/solver123",
            any_custom_metadata=[MetadataFilterItem(name="solver_type", pattern="FEM")],
        ),
    )

    assert page.meta.total == 1
    assert len(page.data) == 1
    assert page.data[0].uuid == project_uuid

    # Test with pattern match on metadata field
    page = await projects_rpc.list_projects_marked_as_jobs(
        rpc_client=rpc_client,
        product_name=product_name,
        user_id=user_id,
        filters=ListProjectsMarkedAsJobRpcFilters(
            any_custom_metadata=[MetadataFilterItem(name="mesh_cells", pattern="1*")],
        ),
    )

    assert page.meta.total == 1
    assert len(page.data) == 1
    assert page.data[0].uuid == project_uuid

    # Test with multiple metadata fields (any match should return the project)
    page = await projects_rpc.list_projects_marked_as_jobs(
        rpc_client=rpc_client,
        product_name=product_name,
        user_id=user_id,
        filters=ListProjectsMarkedAsJobRpcFilters(
            any_custom_metadata=[
                MetadataFilterItem(name="solver_type", pattern="FEM"),
                MetadataFilterItem(name="non_existent", pattern="value"),
            ],
        ),
    )

    assert page.meta.total == 1
    assert len(page.data) == 1

    # Test with no matches
    page = await projects_rpc.list_projects_marked_as_jobs(
        rpc_client=rpc_client,
        product_name=product_name,
        user_id=user_id,
        filters=ListProjectsMarkedAsJobRpcFilters(
            any_custom_metadata=[
                MetadataFilterItem(name="solver_type", pattern="CFD"),  # No match
            ],
        ),
    )

    assert page.meta.total == 0
    assert len(page.data) == 0

    # Test with combination of resource prefix and metadata
    page = await projects_rpc.list_projects_marked_as_jobs(
        rpc_client=rpc_client,
        product_name=product_name,
        user_id=user_id,
        filters=ListProjectsMarkedAsJobRpcFilters(
            job_parent_resource_name_prefix="wrong/prefix",
            any_custom_metadata=[
                MetadataFilterItem(name="solver_type", pattern="FEM"),
            ],
        ),
    )

    assert page.meta.total == 0
    assert len(page.data) == 0


async def test_rpc_client_get_project_marked_as_job_found(
    rpc_client: RabbitMQRPCClient,
    product_name: ProductName,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
):
    project_uuid = ProjectID(user_project["uuid"])
    user_id = logged_user["id"]
    job_parent_resource_name = "solvers/solver123/version/1.2.3"

    # Mark the project as a job first
    await projects_rpc.mark_project_as_job(
        rpc_client=rpc_client,
        product_name=product_name,
        user_id=user_id,
        project_uuid=project_uuid,
        job_parent_resource_name=job_parent_resource_name,
        storage_assets_deleted=False,
    )

    # Should be able to retrieve it
    project_job = await projects_rpc.get_project_marked_as_job(
        rpc_client=rpc_client,
        product_name=product_name,
        user_id=user_id,
        project_uuid=project_uuid,
        job_parent_resource_name=job_parent_resource_name,
    )
    assert project_job.uuid == project_uuid
    assert project_job.job_parent_resource_name == job_parent_resource_name
    assert project_job.name == user_project["name"]


async def test_rpc_client_get_project_marked_as_job_not_found(
    rpc_client: RabbitMQRPCClient,
    product_name: ProductName,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
):

    project_uuid = ProjectID(user_project["uuid"])
    user_id = logged_user["id"]
    job_parent_resource_name = "solvers/solver123/version/1.2.3"

    # Do NOT mark the project as a job, so it should not be found
    with pytest.raises(ProjectNotFoundRpcError):
        await projects_rpc.get_project_marked_as_job(
            rpc_client=rpc_client,
            product_name=product_name,
            user_id=user_id,
            project_uuid=project_uuid,
            job_parent_resource_name=job_parent_resource_name,
        )


async def test_rpc_client_get_project_marked_as_job_forbidden(
    rpc_client: RabbitMQRPCClient,
    product_name: ProductName,
    logged_user: UserInfoDict,
    other_user: UserInfoDict,
    user_project: ProjectDict,
):
    """
    Ensures ProjectForbiddenRpcError is raised if the user does not have read access to the project.
    """
    project_uuid = ProjectID(user_project["uuid"])
    job_parent_resource_name = "solvers/solver123/version/1.2.3"

    # Mark the project as a job as the owner
    await projects_rpc.mark_project_as_job(
        rpc_client=rpc_client,
        product_name=product_name,
        user_id=logged_user["id"],
        project_uuid=project_uuid,
        job_parent_resource_name=job_parent_resource_name,
        storage_assets_deleted=False,
    )

    # Try to get the project as another user (should not have access)
    with pytest.raises(ProjectForbiddenRpcError):
        await projects_rpc.get_project_marked_as_job(
            rpc_client=rpc_client,
            product_name=product_name,
            user_id=other_user["id"],
            project_uuid=project_uuid,
            job_parent_resource_name=job_parent_resource_name,
        )


async def test_mark_and_get_project_job_storage_assets_deleted(
    rpc_client: RabbitMQRPCClient,
    product_name: ProductName,
    logged_user: UserInfoDict,
    user_project: ProjectDict,
):
    """
    Marks a project as a job with storage_assets_deleted True, checks the value,
    then marks it again with storage_assets_deleted False and checks the value again.
    """
    project_uuid = ProjectID(user_project["uuid"])
    user_id = logged_user["id"]
    job_parent_resource_name = "solvers/solver123/version/1.2.3"

    # First mark as job with storage_assets_deleted=True
    await projects_rpc.mark_project_as_job(
        rpc_client=rpc_client,
        product_name=product_name,
        user_id=user_id,
        project_uuid=project_uuid,
        job_parent_resource_name=job_parent_resource_name,
        storage_assets_deleted=True,
    )

    # Retrieve and check
    project_job = await projects_rpc.get_project_marked_as_job(
        rpc_client=rpc_client,
        product_name=product_name,
        user_id=user_id,
        project_uuid=project_uuid,
        job_parent_resource_name=job_parent_resource_name,
    )
    assert project_job.storage_assets_deleted is True

    # Mark again as job with storage_assets_deleted=False
    await projects_rpc.mark_project_as_job(
        rpc_client=rpc_client,
        product_name=product_name,
        user_id=user_id,
        project_uuid=project_uuid,
        job_parent_resource_name=job_parent_resource_name,
        storage_assets_deleted=False,
    )

    # Retrieve and check again
    project_job = await projects_rpc.get_project_marked_as_job(
        rpc_client=rpc_client,
        product_name=product_name,
        user_id=user_id,
        project_uuid=project_uuid,
        job_parent_resource_name=job_parent_resource_name,
    )
    assert project_job.storage_assets_deleted is False
