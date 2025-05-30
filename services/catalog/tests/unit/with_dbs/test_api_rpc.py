# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import Callable
from typing import Any

import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_catalog.services import (
    ServiceListFilters,
    ServiceUpdateV2,
)
from models_library.products import ProductName
from models_library.rest_pagination import (
    DEFAULT_NUMBER_OF_ITEMS_PER_PAGE,
    MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE,
)
from models_library.services_enums import ServiceType
from models_library.services_history import ServiceRelease
from models_library.services_types import ServiceKey, ServiceVersion
from models_library.users import UserID
from packaging import version
from pydantic import ValidationError
from pytest_simcore.helpers.catalog_services import CreateFakeServiceDataCallable
from pytest_simcore.helpers.faker_factories import random_icon_url
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.typing_env import EnvVarsDict
from respx.router import MockRouter
from servicelib.rabbitmq import RabbitMQRPCClient
from servicelib.rabbitmq.rpc_interfaces.catalog import services as catalog_rpc
from servicelib.rabbitmq.rpc_interfaces.catalog.errors import (
    CatalogForbiddenError,
    CatalogItemNotFoundError,
)

pytest_simcore_core_services_selection = [
    "rabbit",
    "postgres",
]
pytest_simcore_ops_services_selection = []


@pytest.fixture
def app_environment(
    monkeypatch: pytest.MonkeyPatch,
    app_environment: EnvVarsDict,
    rabbit_env_vars_dict: EnvVarsDict,  # rabbitMQ settings from 'rabbit' service
) -> EnvVarsDict:
    monkeypatch.delenv("CATALOG_RABBITMQ", raising=False)
    return setenvs_from_dict(
        monkeypatch,
        {**app_environment, **rabbit_env_vars_dict},
    )


@pytest.fixture
def num_services() -> int:
    return 5


@pytest.fixture
def num_versions_per_service() -> int:
    return 20


@pytest.fixture
def fake_data_for_services(
    target_product: ProductName,
    create_fake_service_data: CreateFakeServiceDataCallable,
    num_services: int,
    num_versions_per_service: int,
) -> list:
    return [
        create_fake_service_data(
            f"simcore/services/comp/test-api-rpc-service-{n}",
            f"{v}.0.0",
            team_access=None,
            everyone_access=None,
            product=target_product,
        )
        for n in range(num_services)
        for v in range(num_versions_per_service)
    ]


@pytest.fixture
def expected_director_rest_api_list_services(
    expected_director_rest_api_list_services: list[dict[str, Any]],
    fake_data_for_services: list,
    create_director_list_services_from: Callable,
) -> list[dict[str, Any]]:
    # OVERRIDES: Changes the values returned by the mocked_director_service_api

    return create_director_list_services_from(
        expected_director_rest_api_list_services, fake_data_for_services
    )


@pytest.fixture
async def background_sync_task_mocked(
    background_task_lifespan_disabled: None,
    services_db_tables_injector: Callable,
    fake_data_for_services: list,
) -> None:
    # inject db services (typically done by the sync background task)
    await services_db_tables_injector(fake_data_for_services)


async def test_rpc_list_services_paginated_with_no_services_returns_empty_page(
    background_sync_task_mocked: None,
    mocked_director_rest_api: MockRouter,
    rpc_client: RabbitMQRPCClient,
    user_id: UserID,
    app: FastAPI,
):
    assert app

    page = await catalog_rpc.list_services_paginated(
        rpc_client, product_name="not_existing_returns_no_services", user_id=user_id
    )
    assert page.data == []
    assert page.links.next is None
    assert page.links.prev is None
    assert page.meta.count == 0
    assert page.meta.total == 0


async def test_rpc_list_services_paginated_with_filters(
    background_sync_task_mocked: None,
    mocked_director_rest_api: MockRouter,
    rpc_client: RabbitMQRPCClient,
    product_name: ProductName,
    user_id: UserID,
    app: FastAPI,
):
    assert app

    # only computational services introduced by the background_sync_task_mocked
    page = await catalog_rpc.list_services_paginated(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        filters={"service_type": "computational"},
    )
    # Fixed: Count might be capped by page limit
    assert page.meta.count <= page.meta.total
    assert page.meta.total > 0

    page = await catalog_rpc.list_services_paginated(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        filters=ServiceListFilters(service_type=ServiceType.DYNAMIC),
    )
    assert page.meta.total == 0


@pytest.mark.skip(
    reason="Issue with mocked_director_rest_api fixture. Urgent feature in master needed. Will follow up."
)
async def test_rpc_list_services_paginated_with_filter_combinations(
    background_sync_task_mocked: None,
    mocked_director_rest_api: MockRouter,
    rpc_client: RabbitMQRPCClient,
    product_name: ProductName,
    user_id: UserID,
    app: FastAPI,
    create_fake_service_data: CreateFakeServiceDataCallable,
    services_db_tables_injector: Callable,
):
    """Tests all combinations of filters for list_services_paginated"""
    # Setup: Create test services with different patterns and types
    test_services = [
        # Computational services
        create_fake_service_data(
            "simcore/services/comp/test-service1",
            "1.0.0",
            team_access=None,
            everyone_access=None,
            product=product_name,
            version_display="2023 Release",
        ),
        create_fake_service_data(
            "simcore/services/comp/test-service2",
            "1.0.0",
            team_access=None,
            everyone_access=None,
            product=product_name,
            version_display=None,
        ),
        # Dynamic services
        create_fake_service_data(
            "simcore/services/dynamic/jupyter-lab",
            "1.0.0",
            team_access=None,
            everyone_access=None,
            product=product_name,
            version_display="2024 Beta",
        ),
        create_fake_service_data(
            "simcore/services/dynamic/jupyter-python",
            "1.0.0",
            team_access=None,
            everyone_access=None,
            product=product_name,
            version_display=None,
        ),
    ]
    await services_db_tables_injector(test_services)

    # Test 1: Filter by service type only
    page = await catalog_rpc.list_services_paginated(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        filters=ServiceListFilters(service_type=ServiceType.COMPUTATIONAL),
    )
    assert page.meta.total == 2
    assert all("services/comp/" in item.key for item in page.data)

    # Test 2: Filter by key pattern only
    page = await catalog_rpc.list_services_paginated(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        filters=ServiceListFilters(service_key_pattern="*/jupyter-*"),
    )
    assert page.meta.total == 2
    assert all("jupyter-" in item.key for item in page.data)

    # Test 3: Filter by version display pattern only
    page = await catalog_rpc.list_services_paginated(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        filters=ServiceListFilters(version_display_pattern="*2023*"),
    )
    assert page.meta.total == 1
    assert page.data[0].version_display == "2023 Release"

    # Test 4: Combined filters - type and key pattern
    page = await catalog_rpc.list_services_paginated(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        filters=ServiceListFilters(
            service_type=ServiceType.DYNAMIC, service_key_pattern="*/jupyter-*"
        ),
    )
    assert page.meta.total == 2
    assert all(
        "services/dynamic/" in item.key and "jupyter-" in item.key for item in page.data
    )

    # Test 5: Combined filters with version display pattern
    page = await catalog_rpc.list_services_paginated(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        filters=ServiceListFilters(
            service_type=ServiceType.DYNAMIC,
            service_key_pattern="*/jupyter-*",
            version_display_pattern="*2024*",
        ),
    )
    assert page.meta.total == 1
    assert page.data[0].key == "simcore/services/dynamic/jupyter-lab"
    assert page.data[0].version_display == "2024 Beta"
    page = await catalog_rpc.list_services_paginated(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        filters=ServiceListFilters(
            service_type=ServiceType.DYNAMIC,
            service_key_pattern="*/jupyter-*",
            version_display_pattern="*2024*",
        ),
    )
    assert page.meta.total == 1
    assert page.data[0].version_display == "2024 Beta"


async def test_rpc_catalog_client_workflow(
    background_sync_task_mocked: None,
    mocked_director_rest_api: MockRouter,
    rpc_client: RabbitMQRPCClient,
    product_name: ProductName,
    user_id: UserID,
    app: FastAPI,
    faker: Faker,
):
    assert app

    page = await catalog_rpc.list_services_paginated(
        rpc_client, product_name=product_name, user_id=user_id
    )

    assert page.data
    service_key = page.data[0].key
    service_version = page.data[0].version

    with pytest.raises(ValidationError):
        await catalog_rpc.list_services_paginated(
            rpc_client,
            product_name=product_name,
            user_id=user_id,
            limit=MAXIMUM_NUMBER_OF_ITEMS_PER_PAGE + 1,
        )

    got = await catalog_rpc.get_service(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
    )
    assert got.key == service_key
    assert got.version == service_version

    assert got.model_dump(exclude={"history"}) == next(
        item.model_dump(exclude={"release"})
        for item in page.data
        if (item.key == service_key and item.version == service_version)
    )

    updated = await catalog_rpc.update_service(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
        update=ServiceUpdateV2(
            name="foo",
            description="bar",
            icon=random_icon_url(faker),
            version_display="this is a nice version",
            description_ui=True,  # owner activates wiki view
        ),
    )

    assert updated.key == got.key
    assert updated.version == got.version
    assert updated.name == "foo"
    assert updated.description == "bar"
    assert updated.description_ui
    assert updated.version_display == "this is a nice version"
    assert updated.icon is not None
    assert not updated.classifiers

    got = await catalog_rpc.get_service(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
    )
    assert got == updated


async def test_rpc_get_service_not_found_error(
    background_sync_task_mocked: None,
    mocked_director_rest_api: MockRouter,
    app: FastAPI,
    rpc_client: RabbitMQRPCClient,
    product_name: ProductName,
    user_id: UserID,
):

    with pytest.raises(CatalogItemNotFoundError, match="unknown"):
        await catalog_rpc.get_service(
            rpc_client,
            product_name=product_name,
            user_id=user_id,
            service_key="simcore/services/dynamic/unknown",
            service_version="1.0.0",
        )


async def test_rpc_get_service_validation_error(
    background_sync_task_mocked: None,
    mocked_director_rest_api: MockRouter,
    app: FastAPI,
    rpc_client: RabbitMQRPCClient,
    product_name: ProductName,
    user_id: UserID,
):

    with pytest.raises(ValidationError, match="service_key"):
        await catalog_rpc.get_service(
            rpc_client,
            product_name=product_name,
            user_id=user_id,
            service_key="wrong-format/unknown",
            service_version="1.0.0",
        )


async def test_rpc_check_for_service(
    background_sync_task_mocked: None,
    mocked_director_rest_api: MockRouter,
    app: FastAPI,
    rpc_client: RabbitMQRPCClient,
    product_name: ProductName,
    user_id: UserID,
):
    with pytest.raises(CatalogItemNotFoundError, match="unknown"):
        await catalog_rpc.check_for_service(
            rpc_client,
            product_name=product_name,
            user_id=user_id,
            service_key="simcore/services/dynamic/unknown",
            service_version="1.0.0",
        )


async def test_rpc_get_service_access_rights(
    background_sync_task_mocked: None,
    mocked_director_rest_api: MockRouter,
    rpc_client: RabbitMQRPCClient,
    product_name: ProductName,
    user: dict[str, Any],
    user_id: UserID,
    other_user: dict[str, Any],
    app: FastAPI,
):
    assert app
    assert user["id"] == user_id

    # user_id owns a service (created in background_sync_task_mocked)
    service_key = ServiceKey("simcore/services/comp/test-api-rpc-service-0")
    service_version = ServiceVersion("0.0.0")

    service = await catalog_rpc.get_service(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
    )
    assert service
    assert service.access_rights
    assert service.access_rights[user["primary_gid"]].write
    assert service.access_rights[user["primary_gid"]].execute

    assert other_user["primary_gid"] not in service.access_rights

    # other_user does not have EXECUTE access -----------------
    with pytest.raises(CatalogForbiddenError, match=service_key):
        await catalog_rpc.get_service(
            rpc_client,
            product_name=product_name,
            user_id=other_user["id"],
            service_key=service_key,
            service_version=service_version,
        )

    # other_user does not have WRITE access
    with pytest.raises(CatalogForbiddenError, match=service_key):
        await catalog_rpc.update_service(
            rpc_client,
            product_name=product_name,
            user_id=other_user["id"],
            service_key=service_key,
            service_version=service_version,
            update={
                "name": "foo",
                "description": "bar",
            },
        )

    # user_id gives "x access" to other_user ------------
    assert service.access_rights is not None
    await catalog_rpc.update_service(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
        update={
            "access_rights": {
                **service.access_rights,
                other_user["primary_gid"]: {
                    "execute": True,
                    "write": False,
                },
            }
        },
    )

    # other user can now GET but NOT UPDATE
    await catalog_rpc.get_service(
        rpc_client,
        product_name=product_name,
        user_id=other_user["id"],
        service_key=service_key,
        service_version=service_version,
    )

    with pytest.raises(CatalogForbiddenError, match=service_key):
        await catalog_rpc.update_service(
            rpc_client,
            product_name=product_name,
            user_id=other_user["id"],
            service_key=service_key,
            service_version=service_version,
            update={
                "name": "foo",
                "description": "bar",
            },
        )

    # user_id gives "xw access" to other_user ------------------
    assert service.access_rights is not None
    await catalog_rpc.update_service(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
        update={
            "access_rights": {
                **service.access_rights,
                other_user["primary_gid"]: {
                    "execute": True,
                    "write": True,
                },
            }
        },
    )

    # other_user can now update and get
    await catalog_rpc.update_service(
        rpc_client,
        product_name=product_name,
        user_id=other_user["id"],
        service_key=service_key,
        service_version=service_version,
        update={
            "name": "foo",
            "description": "bar",
        },
    )
    updated_service = await catalog_rpc.get_service(
        rpc_client,
        product_name=product_name,
        user_id=other_user["id"],
        service_key=service_key,
        service_version=service_version,
    )
    assert updated_service.model_dump(include={"name", "description"}) == {
        "name": "foo",
        "description": "bar",
    }


async def test_rpc_batch_get_my_services(
    background_sync_task_mocked: None,
    mocked_director_rest_api: MockRouter,
    rpc_client: RabbitMQRPCClient,
    product_name: ProductName,
    user: dict[str, Any],
    user_id: UserID,
    app: FastAPI,
    create_fake_service_data: CreateFakeServiceDataCallable,
    services_db_tables_injector: Callable,
):
    # Create fake services data
    service_key = "simcore/services/comp/test-batch-service"
    service_version_1 = "1.0.0"
    service_version_2 = "1.0.5"

    other_service_key = "simcore/services/comp/other-batch-service"
    other_service_version = "1.0.0"

    fake_service_1 = create_fake_service_data(
        service_key,
        service_version_1,
        team_access=None,
        everyone_access=None,
        product=product_name,
    )
    fake_service_2 = create_fake_service_data(
        service_key,
        service_version_2,
        team_access="x",
        everyone_access=None,
        product=product_name,
    )
    fake_service_3 = create_fake_service_data(
        other_service_key,
        other_service_version,
        team_access=None,
        everyone_access=None,
        product=product_name,
    )

    # Inject fake services into the database
    await services_db_tables_injector([fake_service_1, fake_service_2, fake_service_3])

    # Batch get my services: project with two, not three
    ids = [
        (service_key, service_version_1),
        (other_service_key, other_service_version),
    ]

    my_services = await catalog_rpc.batch_get_my_services(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        ids=ids,
    )

    assert len(my_services) == 2

    # Check access rights to all of them
    assert my_services[0].my_access_rights.model_dump() == {
        "execute": True,
        "write": True,
    }
    assert my_services[0].owner == user["primary_gid"]
    assert my_services[0].key == service_key
    assert my_services[0].release.version == service_version_1
    assert my_services[0].release.compatibility
    assert (
        my_services[0].release.compatibility.can_update_to.version == service_version_2
    )

    assert my_services[1].my_access_rights.model_dump() == {
        "execute": True,
        "write": True,
    }
    assert my_services[1].owner == user["primary_gid"]
    assert my_services[1].key == other_service_key
    assert my_services[1].release.version == other_service_version


async def test_rpc_list_my_service_history_paginated(
    background_sync_task_mocked: None,
    mocked_director_rest_api: MockRouter,
    rpc_client: RabbitMQRPCClient,
    product_name: ProductName,
    user_id: UserID,
    app: FastAPI,
    create_fake_service_data: CreateFakeServiceDataCallable,
    services_db_tables_injector: Callable,
):
    assert app

    service_key = "simcore/services/comp/test-service-release-history"
    service_version_1 = "1.0.0"
    service_version_2 = "1.1.0"

    assert version.Version(service_version_1) < version.Version(service_version_2)

    # Inject fake service releases for the target service
    fake_releases = [
        create_fake_service_data(
            service_key,
            srv_version,
            team_access=None,
            everyone_access=None,
            product=product_name,
        )
        for srv_version in (service_version_1, service_version_2)
    ]

    # Inject unrelated fake service releases
    unrelated_service_key_1 = "simcore/services/comp/unrelated-service-1"
    unrelated_service_key_2 = "simcore/services/comp/unrelated-service-2"
    unrelated_releases = [
        *[
            create_fake_service_data(
                unrelated_service_key_1,
                srv_version,
                team_access=None,
                everyone_access=None,
                product=product_name,
            )
            for srv_version in (service_version_1, service_version_2)
        ],
        create_fake_service_data(
            unrelated_service_key_2,
            "2.0.0",
            team_access=None,
            everyone_access=None,
            product=product_name,
        ),
    ]

    await services_db_tables_injector(fake_releases + unrelated_releases)

    # Call the RPC function
    page = await catalog_rpc.list_my_service_history_latest_first(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
    )
    release_history: list[ServiceRelease] = page.data

    # Validate the response
    assert isinstance(release_history, list)
    assert len(release_history) == 2
    assert release_history[0].version == service_version_2, "expected newest first"
    assert release_history[1].version == service_version_1


async def test_rpc_get_service_ports_successful_retrieval(
    background_sync_task_mocked: None,
    mocked_director_rest_api: MockRouter,
    rpc_client: RabbitMQRPCClient,
    product_name: ProductName,
    user_id: UserID,
    app: FastAPI,
    expected_director_rest_api_list_services: list[dict[str, Any]],
):
    """Tests successful retrieval of service ports for a specific service version"""
    assert app

    # Create a service with known ports
    expected_service = expected_director_rest_api_list_services[0]
    service_key = expected_service["key"]
    service_version = expected_service["version"]

    # Call the RPC function to get service ports
    ports = await catalog_rpc.get_service_ports(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        service_key=service_key,
        service_version=service_version,
    )

    # Validate the response
    expected_inputs = expected_service["inputs"]
    expected_outputs = expected_service["outputs"]
    assert len(ports) == len(expected_inputs) + len(expected_outputs)


async def test_rpc_get_service_ports_not_found(
    background_sync_task_mocked: None,
    mocked_director_rest_api: MockRouter,
    rpc_client: RabbitMQRPCClient,
    product_name: ProductName,
    user_id: UserID,
    app: FastAPI,
):
    """Tests that appropriate error is raised when service does not exist"""
    assert app

    service_version = "1.0.0"
    non_existent_key = "simcore/services/comp/non-existent-service"

    # Test service not found scenario
    with pytest.raises(CatalogItemNotFoundError, match="non-existent-service"):
        await catalog_rpc.get_service_ports(
            rpc_client,
            product_name=product_name,
            user_id=user_id,
            service_key=non_existent_key,
            service_version=service_version,
        )


async def test_rpc_get_service_ports_permission_denied(
    background_sync_task_mocked: None,
    mocked_director_rest_api: MockRouter,
    rpc_client: RabbitMQRPCClient,
    product_name: ProductName,
    user: dict[str, Any],
    user_id: UserID,
    other_user: dict[str, Any],
    app: FastAPI,
    create_fake_service_data: CreateFakeServiceDataCallable,
    services_db_tables_injector: Callable,
):
    """Tests that appropriate error is raised when user doesn't have permission"""
    assert app

    assert other_user["id"] != user_id
    assert user["id"] == user_id

    # Create a service with restricted access
    restricted_service_key = "simcore/services/comp/restricted-service"
    service_version = "1.0.0"

    fake_restricted_service = create_fake_service_data(
        restricted_service_key,
        service_version,
        team_access=None,
        everyone_access=None,
        product=product_name,
    )

    # Modify access rights to restrict access
    # Remove user's access if present
    if (
        "access_rights" in fake_restricted_service
        and user["primary_gid"] in fake_restricted_service["access_rights"]
    ):
        fake_restricted_service["access_rights"].pop(user["primary_gid"])

    await services_db_tables_injector([fake_restricted_service])

    # Attempt to access without permission
    with pytest.raises(CatalogForbiddenError):
        await catalog_rpc.get_service_ports(
            rpc_client,
            product_name=product_name,
            user_id=other_user["id"],  # Use a different user ID
            service_key=restricted_service_key,
            service_version=service_version,
        )


async def test_rpc_get_service_ports_validation_error(
    background_sync_task_mocked: None,
    mocked_director_rest_api: MockRouter,
    rpc_client: RabbitMQRPCClient,
    product_name: ProductName,
    user_id: UserID,
    app: FastAPI,
):
    """Tests validation error handling for list_all_services_summaries_paginated."""
    assert app

    # Test with invalid service key format
    with pytest.raises(ValidationError, match="service_key"):
        await catalog_rpc.get_service_ports(
            rpc_client,
            product_name=product_name,
            user_id=user_id,
            service_key="invalid-service-key-format",
            service_version="1.0.0",
        )


async def test_rpc_list_all_services_summaries_paginated_with_no_services_returns_empty_page(
    background_sync_task_mocked: None,
    mocked_director_rest_api: MockRouter,
    rpc_client: RabbitMQRPCClient,
    user_id: UserID,
    app: FastAPI,
):
    """Tests that requesting summaries for non-existing services returns an empty page."""
    assert app

    page = await catalog_rpc.list_all_services_summaries_paginated(
        rpc_client, product_name="not_existing_returns_no_services", user_id=user_id
    )
    assert page.data == []
    assert page.links.next is None
    assert page.links.prev is None
    assert page.meta.count == 0
    assert page.meta.total == 0


async def test_rpc_list_all_services_summaries_paginated_with_filters(
    background_sync_task_mocked: None,
    mocked_director_rest_api: MockRouter,
    rpc_client: RabbitMQRPCClient,
    product_name: ProductName,
    user_id: UserID,
    app: FastAPI,
):
    """Tests that service summaries can be filtered by service type."""
    assert app

    # Get all computational services introduced by the background_sync_task_mocked
    page = await catalog_rpc.list_all_services_summaries_paginated(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        filters={"service_type": "computational"},
    )
    # Fixed: Count might be capped by page limit
    assert page.meta.count <= page.meta.total
    assert page.meta.total > 0

    # All items should be service summaries with the expected minimal fields
    for item in page.data:
        assert "key" in item.model_dump()
        assert "name" in item.model_dump()
        assert "version" in item.model_dump()
        assert "description" in item.model_dump()

    # Filter for a service type that doesn't exist
    page = await catalog_rpc.list_all_services_summaries_paginated(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        filters=ServiceListFilters(service_type=ServiceType.DYNAMIC),
    )
    assert page.meta.total == 0


async def test_rpc_list_all_services_summaries_paginated_with_pagination(
    background_sync_task_mocked: None,
    mocked_director_rest_api: MockRouter,
    rpc_client: RabbitMQRPCClient,
    product_name: ProductName,
    user_id: UserID,
    app: FastAPI,
    num_services: int,
    num_versions_per_service: int,
):
    """Tests pagination of service summaries."""
    assert app

    total_services = num_services * num_versions_per_service

    # Get first page with default page size
    first_page = await catalog_rpc.list_all_services_summaries_paginated(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
    )

    # Verify total count is correct
    assert first_page.meta.total == total_services

    # Maximum items per page is constrained by DEFAULT_NUMBER_OF_ITEMS_PER_PAGE
    assert len(first_page.data) <= DEFAULT_NUMBER_OF_ITEMS_PER_PAGE

    # Test with small page size
    page_size = 5
    first_small_page = await catalog_rpc.list_all_services_summaries_paginated(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        limit=page_size,
        offset=0,
    )
    assert len(first_small_page.data) == page_size
    assert first_small_page.meta.total == total_services
    assert first_small_page.links.next is not None
    assert first_small_page.links.prev is None

    # Get next page and verify different content
    next_page = await catalog_rpc.list_all_services_summaries_paginated(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
        limit=page_size,
        offset=page_size,
    )
    assert len(next_page.data) == page_size
    assert next_page.meta.total == first_small_page.meta.total

    # Check that first and second page contain different items
    first_page_keys = {(item.key, item.version) for item in first_small_page.data}
    next_page_keys = {(item.key, item.version) for item in next_page.data}
    assert not first_page_keys.intersection(next_page_keys)


async def test_rpc_compare_latest_vs_all_services_summaries(
    background_sync_task_mocked: None,
    mocked_director_rest_api: MockRouter,
    rpc_client: RabbitMQRPCClient,
    product_name: ProductName,
    user_id: UserID,
    app: FastAPI,
    num_services: int,
    num_versions_per_service: int,
):
    """Compares results of list_services_paginated vs list_all_services_summaries_paginated."""
    assert app

    total_expected_services = num_services * num_versions_per_service

    # Get all latest services (should fit in one page)
    latest_page = await catalog_rpc.list_services_paginated(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
    )
    assert latest_page.meta.total == num_services

    # For all services (all versions), we might need multiple requests
    # First page to get metadata
    first_all_page = await catalog_rpc.list_all_services_summaries_paginated(
        rpc_client,
        product_name=product_name,
        user_id=user_id,
    )
    assert first_all_page.meta.total == total_expected_services

    # Collect all items across multiple pages if needed
    all_items = list(first_all_page.data)
    offset = len(all_items)

    # Continue fetching pages until we have all items
    while offset < total_expected_services:
        next_page = await catalog_rpc.list_all_services_summaries_paginated(
            rpc_client,
            product_name=product_name,
            user_id=user_id,
            offset=offset,
        )
        all_items.extend(next_page.data)
        offset += len(next_page.data)
        if not next_page.links.next:
            break

    # Verify we got all items
    assert len(all_items) == total_expected_services

    # Collect unique keys from both responses
    latest_keys = {item.key for item in latest_page.data}
    all_keys = {item.key for item in all_items}

    # All service keys in latest should be in all services
    assert latest_keys.issubset(all_keys)

    # For each key in latest, there should be exactly num_versions_per_service entries in all
    for key in latest_keys:
        versions_in_all = [item.version for item in all_items if item.key == key]
        assert len(versions_in_all) == num_versions_per_service

        # Get the latest version from latest_page
        latest_version = next(
            item.version for item in latest_page.data if item.key == key
        )

        # Verify this version exists in versions_in_all
        assert latest_version in versions_in_all

    # Verify all items are ServiceSummary objects with just the essential fields
    for item in all_items:
        item_dict = item.model_dump()
        assert "key" in item_dict
        assert "version" in item_dict
        assert "name" in item_dict
        assert "description" in item_dict
        assert "thumbnail" not in item_dict
        assert "service_type" not in item_dict
        assert "inputs" not in item_dict
        assert "outputs" not in item_dict
        assert "access_rights" not in item_dict
