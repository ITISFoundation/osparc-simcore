# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-positional-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import pytest
import respx
from faker import Faker
from fastapi.encoders import jsonable_encoder
from models_library.api_schemas_catalog.services_specifications import (
    ServiceSpecifications,
)
from models_library.generated_models.docker_rest_api import (
    DiscreteResourceSpec,
    GenericResource,
    GenericResources,
    Limit,
    NamedResourceSpec,
    ResourceObject,
)
from models_library.generated_models.docker_rest_api import (
    Resources1 as ServiceTaskResources,
)
from models_library.generated_models.docker_rest_api import ServiceSpec, TaskSpec
from models_library.products import ProductName
from models_library.users import UserID
from simcore_postgres_database.models.groups import user_to_groups
from simcore_postgres_database.models.services_specifications import (
    services_specifications,
)
from simcore_service_catalog.models.services_specifications import (
    ServiceSpecificationsAtDB,
)
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette import status
from starlette.testclient import TestClient
from yarl import URL

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture
async def services_specifications_injector(
    sqlalchemy_async_engine: AsyncEngine,
) -> AsyncIterator[Callable[[ServiceSpecificationsAtDB], Awaitable[None]]]:
    inserted_specs: list[ServiceSpecificationsAtDB] = []

    async def _injector(
        service_spec: ServiceSpecificationsAtDB,
    ):
        async with sqlalchemy_async_engine.begin() as conn:
            await conn.execute(
                services_specifications.insert().values(jsonable_encoder(service_spec))
            )
        inserted_specs.append(service_spec)

    yield _injector

    # clean up
    async with sqlalchemy_async_engine.begin() as conn:
        for spec in inserted_specs:
            await conn.execute(
                services_specifications.delete().where(
                    (services_specifications.c.service_key == spec.service_key)
                    & (
                        services_specifications.c.service_version
                        == spec.service_version
                    )
                    & (services_specifications.c.gid == spec.gid)
                )
            )


@pytest.fixture
def create_service_specifications(
    faker: Faker,
) -> Callable[..., ServiceSpecificationsAtDB]:
    def _creator(service_key, service_version, gid) -> ServiceSpecificationsAtDB:
        return ServiceSpecificationsAtDB(
            service_key=service_key,
            service_version=service_version,
            gid=gid,
            sidecar=ServiceSpec(Labels=faker.pydict(allowed_types=(str,))),
            service=ServiceSpec(
                TaskTemplate=TaskSpec(
                    Resources=ServiceTaskResources(
                        Limits=Limit(
                            NanoCPUs=faker.pyint(),
                            MemoryBytes=faker.pyint(),
                            Pids=faker.pyint(),
                        ),
                        Reservations=ResourceObject(
                            NanoCPUs=faker.pyint(),
                            MemoryBytes=faker.pyint(),
                            GenericResources=GenericResources(
                                root=[
                                    GenericResource(
                                        NamedResourceSpec=NamedResourceSpec(
                                            Kind=faker.pystr(), Value=faker.pystr()
                                        ),
                                        DiscreteResourceSpec=DiscreteResourceSpec(
                                            Kind=faker.pystr(), Value=faker.pyint()
                                        ),
                                    )
                                ]
                            ),
                        ),
                    )
                )
            ),
        )

    return _creator


async def test_get_service_specifications_returns_403_if_user_does_not_exist(
    background_tasks_setup_disabled,
    mocked_director_service_api: respx.MockRouter,
    rabbitmq_and_rpc_setup_disabled: None,
    client: TestClient,
    user_id: UserID,
    faker: Faker,
):
    service_key = (
        f"simcore/services/{faker.random_element(['comp', 'dynamic'])}/jupyter-math"
    )
    service_version = (
        f"{faker.random_int(0,100)}.{faker.random_int(0,100)}.{faker.random_int(0,100)}"
    )
    url = URL(
        f"/v0/services/{service_key}/{service_version}/specifications"
    ).with_query(user_id=user_id)
    response = client.get(f"{url}")
    assert response.status_code == status.HTTP_403_FORBIDDEN


async def test_get_service_specifications_of_unknown_service_returns_default_specs(
    background_tasks_setup_disabled,
    mocked_director_service_api: respx.MockRouter,
    rabbitmq_and_rpc_setup_disabled: None,
    client: TestClient,
    user_id: UserID,
    user: dict[str, Any],
    faker: Faker,
):
    service_key = f"simcore/services/{faker.random_element(['comp', 'dynamic'])}/{faker.pystr().lower()}"
    service_version = (
        f"{faker.random_int(0,100)}.{faker.random_int(0,100)}.{faker.random_int(0,100)}"
    )
    url = URL(
        f"/v0/services/{service_key}/{service_version}/specifications"
    ).with_query(user_id=user_id)
    response = client.get(f"{url}")
    assert response.status_code == status.HTTP_200_OK
    service_specs = ServiceSpecifications.model_validate(response.json())
    assert service_specs

    assert (
        service_specs.model_dump()
        == client.app.state.settings.CATALOG_SERVICES_DEFAULT_SPECIFICATIONS.model_dump()
    )


async def test_get_service_specifications(
    background_tasks_setup_disabled,
    mocked_director_service_api: respx.MockRouter,
    rabbitmq_and_rpc_setup_disabled: None,
    client: TestClient,
    user_id: UserID,
    user: dict[str, Any],
    user_groups_ids: list[int],
    target_product: ProductName,
    create_fake_service_data: Callable,
    services_db_tables_injector: Callable,
    services_specifications_injector: Callable,
    sqlalchemy_async_engine: AsyncEngine,
    create_service_specifications: Callable[..., ServiceSpecificationsAtDB],
):
    SERVICE_KEY = "simcore/services/dynamic/jupyterlab"
    SERVICE_VERSION = "0.0.1"
    await services_db_tables_injector(
        [
            create_fake_service_data(
                SERVICE_KEY,
                SERVICE_VERSION,
                team_access=None,
                everyone_access=None,
                product=target_product,
            )
        ]
    )

    url = URL(
        f"/v0/services/{SERVICE_KEY}/{SERVICE_VERSION}/specifications"
    ).with_query(user_id=user_id)

    # this should now return default specs since there are none in the db
    response = client.get(f"{url}")
    assert response.status_code == status.HTTP_200_OK
    service_specs = ServiceSpecifications.model_validate(response.json())
    assert service_specs
    assert (
        service_specs.model_dump()
        == client.app.state.settings.CATALOG_SERVICES_DEFAULT_SPECIFICATIONS.model_dump()
    )

    everyone_gid, user_gid, team_gid = user_groups_ids
    # let's inject some rights for everyone group
    everyone_service_specs = create_service_specifications(
        SERVICE_KEY, SERVICE_VERSION, everyone_gid
    )
    await services_specifications_injector(everyone_service_specs)
    response = client.get(f"{url}")
    assert response.status_code == status.HTTP_200_OK
    service_specs = ServiceSpecifications.model_validate(response.json())
    assert service_specs
    assert service_specs == ServiceSpecifications.model_validate(
        everyone_service_specs.model_dump()
    )

    # let's inject some rights in a standard group, user is not part of that group yet, so it should still return only everyone
    standard_group_service_specs = create_service_specifications(
        SERVICE_KEY, SERVICE_VERSION, team_gid
    )
    await services_specifications_injector(standard_group_service_specs)
    response = client.get(f"{url}")
    assert response.status_code == status.HTTP_200_OK
    service_specs = ServiceSpecifications.model_validate(response.json())
    assert service_specs
    assert service_specs == ServiceSpecifications.model_validate(
        everyone_service_specs.model_dump()
    )

    # put the user in that group now and try again
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(user_to_groups.insert().values(uid=user_id, gid=team_gid))
    response = client.get(f"{url}")
    assert response.status_code == status.HTTP_200_OK
    service_specs = ServiceSpecifications.model_validate(response.json())
    assert service_specs
    assert service_specs == ServiceSpecifications.model_validate(
        standard_group_service_specs.model_dump()
    )

    # now add some other spec in the primary gid, this takes precedence
    user_group_service_specs = create_service_specifications(
        SERVICE_KEY, SERVICE_VERSION, user_gid
    )
    await services_specifications_injector(user_group_service_specs)
    response = client.get(f"{url}")
    assert response.status_code == status.HTTP_200_OK
    service_specs = ServiceSpecifications.model_validate(response.json())
    assert service_specs
    assert service_specs == ServiceSpecifications.model_validate(
        user_group_service_specs.model_dump()
    )


async def test_get_service_specifications_are_passed_to_newer_versions_of_service(
    background_tasks_setup_disabled,
    mocked_director_service_api: respx.MockRouter,
    rabbitmq_and_rpc_setup_disabled: None,
    client: TestClient,
    user_id: UserID,
    user: dict[str, Any],
    user_groups_ids: list[int],
    target_product: ProductName,
    create_fake_service_data: Callable,
    services_db_tables_injector: Callable,
    services_specifications_injector: Callable,
    create_service_specifications: Callable[..., ServiceSpecificationsAtDB],
):
    SERVICE_KEY = "simcore/services/dynamic/jupyterlab"
    sorted_versions = [
        "0.0.1",
        "0.0.2",
        "0.1.0",
        "0.1.1",
        "0.2.3",
        "1.0.0",
        "1.0.1",
        "1.0.10",
        "1.1.1",
        "1.10.1",
        "1.11.1",
        "10.0.0",
    ]
    await asyncio.gather(
        *[
            services_db_tables_injector(
                [
                    create_fake_service_data(
                        SERVICE_KEY,
                        version,
                        team_access=None,
                        everyone_access=None,
                        product=target_product,
                    )
                ]
            )
            for version in sorted_versions
        ]
    )

    everyone_gid, user_gid, team_gid = user_groups_ids
    # let's inject some rights for everyone group ONLY for some versions
    INDEX_FIRST_SERVICE_VERSION_WITH_SPEC = 2
    INDEX_SECOND_SERVICE_VERSION_WITH_SPEC = 6
    versions_with_specs = [
        sorted_versions[INDEX_FIRST_SERVICE_VERSION_WITH_SPEC],
        sorted_versions[INDEX_SECOND_SERVICE_VERSION_WITH_SPEC],
    ]
    version_speced: list[ServiceSpecificationsAtDB] = []

    for version in versions_with_specs:
        specs = create_service_specifications(SERVICE_KEY, version, everyone_gid)
        await services_specifications_injector(specs)
        version_speced.append(specs)

    # check versions before first speced service return the default
    for version in sorted_versions[:INDEX_FIRST_SERVICE_VERSION_WITH_SPEC]:
        url = URL(f"/v0/services/{SERVICE_KEY}/{version}/specifications").with_query(
            user_id=user_id
        )
        response = client.get(f"{url}")
        assert response.status_code == status.HTTP_200_OK
        service_specs = ServiceSpecifications.model_validate(response.json())
        assert service_specs
        assert (
            service_specs.model_dump()
            == client.app.state.settings.CATALOG_SERVICES_DEFAULT_SPECIFICATIONS.model_dump()
        )

    # check version between first index and second all return the specs of the first
    for version in sorted_versions[
        INDEX_FIRST_SERVICE_VERSION_WITH_SPEC:INDEX_SECOND_SERVICE_VERSION_WITH_SPEC
    ]:
        url = URL(f"/v0/services/{SERVICE_KEY}/{version}/specifications").with_query(
            user_id=user_id
        )
        response = client.get(f"{url}")
        assert response.status_code == status.HTTP_200_OK
        service_specs = ServiceSpecifications.model_validate(response.json())
        assert service_specs
        assert service_specs == ServiceSpecifications.model_validate(
            version_speced[0].model_dump()
        ), f"specifications for {version=} are not passed down from {sorted_versions[INDEX_FIRST_SERVICE_VERSION_WITH_SPEC]}"

    # check version from second to last use the second version
    for version in sorted_versions[INDEX_SECOND_SERVICE_VERSION_WITH_SPEC:]:
        url = URL(f"/v0/services/{SERVICE_KEY}/{version}/specifications").with_query(
            user_id=user_id
        )
        response = client.get(f"{url}")
        assert response.status_code == status.HTTP_200_OK
        service_specs = ServiceSpecifications.model_validate(response.json())
        assert service_specs
        assert service_specs == ServiceSpecifications.model_validate(
            version_speced[1].model_dump()
        ), f"specifications for {version=} are not passed down from {sorted_versions[INDEX_SECOND_SERVICE_VERSION_WITH_SPEC]}"

    # if we call with the strict parameter set to true, then we should only get the specs for the one that were specified
    for version in sorted_versions:
        url = URL(f"/v0/services/{SERVICE_KEY}/{version}/specifications").with_query(
            user_id=user_id, strict=1
        )
        response = client.get(f"{url}")
        assert response.status_code == status.HTTP_200_OK
        service_specs = ServiceSpecifications.model_validate(response.json())
        assert service_specs
        if version in versions_with_specs:
            assert (
                service_specs
                != client.app.state.settings.CATALOG_SERVICES_DEFAULT_SPECIFICATIONS
            )
        else:
            assert (
                service_specs
                == client.app.state.settings.CATALOG_SERVICES_DEFAULT_SPECIFICATIONS
            )
