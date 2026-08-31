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
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from models_library.api_schemas_catalog.services_specifications import (
    ServiceSpecifications,
    ServiceSpecificationsGet,
)
from models_library.generated_models.docker_rest_api import (
    DiscreteResourceSpec,
    GenericResource,
    GenericResources,
    Limit,
    NamedResourceSpec,
    ResourceObject,
    ServiceSpec,
    TaskSpec,
)
from models_library.generated_models.docker_rest_api import (
    Resources1 as ServiceTaskResources,
)
from models_library.products import ProductName
from models_library.users import UserID
from pytest_simcore.helpers.catalog_services import CreateFakeServiceDataCallable
from servicelib.rabbitmq.rpc_interfaces.catalog.errors import CatalogForbiddenRpcError
from simcore_postgres_database.models.groups import user_to_groups
from simcore_postgres_database.models.services_specifications import (
    services_specifications,
)
from simcore_service_catalog.models.services_specifications import (
    ServiceSpecificationsAtDB,
)
from simcore_service_catalog.repository.groups import GroupsRepository
from simcore_service_catalog.repository.services import ServicesRepository
from simcore_service_catalog.service.catalog_services import (
    get_catalog_service_specifications,
)
from sqlalchemy.ext.asyncio import AsyncEngine

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
            await conn.execute(services_specifications.insert().values(jsonable_encoder(service_spec)))
        inserted_specs.append(service_spec)

    yield _injector

    # clean up
    async with sqlalchemy_async_engine.begin() as conn:
        for spec in inserted_specs:
            await conn.execute(
                services_specifications.delete().where(
                    (services_specifications.c.service_key == spec.service_key)
                    & (services_specifications.c.service_version == spec.service_version)
                    & (services_specifications.c.gid == spec.gid)
                    & (services_specifications.c.product_name == spec.product_name)
                )
            )


@pytest.fixture
def create_service_specifications(
    faker: Faker,
) -> Callable[..., ServiceSpecificationsAtDB]:
    def _creator(
        service_key,
        service_version,
        gid,
        product_name: ProductName,
        comments=None,
    ) -> ServiceSpecificationsAtDB:
        return ServiceSpecificationsAtDB(
            service_key=service_key,
            service_version=service_version,
            gid=gid,
            product_name=product_name,
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
                                        NamedResourceSpec=NamedResourceSpec(Kind=faker.pystr(), Value=faker.pystr()),
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
            comments=comments,
        )

    return _creator


@pytest.fixture
def get_service_specifications(
    app: FastAPI,
    sqlalchemy_async_engine: AsyncEngine,
) -> Callable[..., Awaitable[ServiceSpecificationsGet]]:
    async def _getter(
        *,
        service_key: str,
        service_version: str,
        user_id: UserID,
        product_name: ProductName,
    ) -> ServiceSpecificationsGet:
        return await get_catalog_service_specifications(
            ServicesRepository(sqlalchemy_async_engine),
            GroupsRepository(sqlalchemy_async_engine),
            default_service_specifications=app.state.settings.CATALOG_SERVICES_DEFAULT_SPECIFICATIONS,
            product_name=product_name,
            user_id=user_id,
            service_key=service_key,
            service_version=service_version,
        )

    return _getter


@pytest.fixture
def default_service_specifications(app: FastAPI) -> ServiceSpecifications:
    specs: ServiceSpecifications = app.state.settings.CATALOG_SERVICES_DEFAULT_SPECIFICATIONS
    return specs


async def test_get_service_specifications_raises_if_user_does_not_exist(
    background_task_lifespan_disabled,
    mocked_director_rest_api: respx.MockRouter,
    rabbitmq_and_rpc_setup_disabled: None,
    repository_lifespan_disabled: None,
    get_service_specifications: Callable[..., Awaitable[ServiceSpecificationsGet]],
    user_id: UserID,
    target_product: ProductName,
    faker: Faker,
):
    service_key = f"simcore/services/{faker.random_element(['comp', 'dynamic'])}/jupyter-math"
    service_version = f"{faker.random_int(0, 100)}.{faker.random_int(0, 100)}.{faker.random_int(0, 100)}"

    with pytest.raises(CatalogForbiddenRpcError):
        await get_service_specifications(
            service_key=service_key,
            service_version=service_version,
            user_id=user_id,
            product_name=target_product,
        )


async def test_get_service_specifications_of_unknown_service_returns_default_specs(
    background_task_lifespan_disabled,
    mocked_director_rest_api: respx.MockRouter,
    rabbitmq_and_rpc_setup_disabled: None,
    repository_lifespan_disabled: None,
    get_service_specifications: Callable[..., Awaitable[ServiceSpecificationsGet]],
    default_service_specifications: ServiceSpecifications,
    user_id: UserID,
    user: dict[str, Any],
    target_product: ProductName,
    faker: Faker,
):
    service_key = f"simcore/services/{faker.random_element(['comp', 'dynamic'])}/{faker.pystr().lower()}"
    service_version = f"{faker.random_int(0, 100)}.{faker.random_int(0, 100)}.{faker.random_int(0, 100)}"

    service_specs = await get_service_specifications(
        service_key=service_key,
        service_version=service_version,
        user_id=user_id,
        product_name=target_product,
    )
    assert service_specs.model_dump() == default_service_specifications.model_dump()


async def test_get_service_specifications(
    background_task_lifespan_disabled,
    mocked_director_rest_api: respx.MockRouter,
    rabbitmq_and_rpc_setup_disabled: None,
    repository_lifespan_disabled: None,
    get_service_specifications: Callable[..., Awaitable[ServiceSpecificationsGet]],
    default_service_specifications: ServiceSpecifications,
    user_id: UserID,
    user: dict[str, Any],
    user_groups_ids: list[int],
    target_product: ProductName,
    create_fake_service_data: CreateFakeServiceDataCallable,
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

    async def _get() -> ServiceSpecificationsGet:
        return await get_service_specifications(
            service_key=SERVICE_KEY,
            service_version=SERVICE_VERSION,
            user_id=user_id,
            product_name=target_product,
        )

    # this should now return default specs since there are none in the db
    assert (await _get()).model_dump() == default_service_specifications.model_dump()

    everyone_gid, user_gid, team_gid = user_groups_ids
    # let's inject some rights for everyone group
    everyone_service_specs = create_service_specifications(SERVICE_KEY, SERVICE_VERSION, everyone_gid, target_product)
    await services_specifications_injector(everyone_service_specs)
    assert await _get() == ServiceSpecificationsGet.model_validate(everyone_service_specs.model_dump())

    # let's inject some rights in a standard group, user is not part of that group yet,
    # so it should still return only everyone
    standard_group_service_specs = create_service_specifications(SERVICE_KEY, SERVICE_VERSION, team_gid, target_product)
    await services_specifications_injector(standard_group_service_specs)
    assert await _get() == ServiceSpecificationsGet.model_validate(everyone_service_specs.model_dump())

    # put the user in that group now and try again
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(user_to_groups.insert().values(uid=user_id, gid=team_gid))
    assert await _get() == ServiceSpecificationsGet.model_validate(standard_group_service_specs.model_dump())

    # now add some other spec in the primary gid, this takes precedence
    user_group_service_specs = create_service_specifications(SERVICE_KEY, SERVICE_VERSION, user_gid, target_product)
    await services_specifications_injector(user_group_service_specs)
    assert await _get() == ServiceSpecificationsGet.model_validate(user_group_service_specs.model_dump())


async def test_get_service_specifications_are_passed_to_newer_versions_of_service(
    background_task_lifespan_disabled,
    mocked_director_rest_api: respx.MockRouter,
    rabbitmq_and_rpc_setup_disabled: None,
    repository_lifespan_disabled: None,
    get_service_specifications: Callable[..., Awaitable[ServiceSpecificationsGet]],
    default_service_specifications: ServiceSpecifications,
    user_id: UserID,
    user: dict[str, Any],
    user_groups_ids: list[int],
    target_product: ProductName,
    create_fake_service_data: CreateFakeServiceDataCallable,
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

    everyone_gid, _user_gid, _team_gid = user_groups_ids
    # let's inject some rights for everyone group ONLY for some versions
    INDEX_FIRST_SERVICE_VERSION_WITH_SPEC = 2
    INDEX_SECOND_SERVICE_VERSION_WITH_SPEC = 6
    versions_with_specs = [
        sorted_versions[INDEX_FIRST_SERVICE_VERSION_WITH_SPEC],
        sorted_versions[INDEX_SECOND_SERVICE_VERSION_WITH_SPEC],
    ]
    version_speced: list[ServiceSpecificationsAtDB] = []

    for version in versions_with_specs:
        specs = create_service_specifications(SERVICE_KEY, version, everyone_gid, target_product)
        await services_specifications_injector(specs)
        version_speced.append(specs)

    # check versions before first speced service return the default
    for version in sorted_versions[:INDEX_FIRST_SERVICE_VERSION_WITH_SPEC]:
        service_specs = await get_service_specifications(
            service_key=SERVICE_KEY,
            service_version=version,
            user_id=user_id,
            product_name=target_product,
        )
        assert service_specs.model_dump() == default_service_specifications.model_dump()

    # check version between first index and second all return the specs of the first
    for version in sorted_versions[INDEX_FIRST_SERVICE_VERSION_WITH_SPEC:INDEX_SECOND_SERVICE_VERSION_WITH_SPEC]:
        service_specs = await get_service_specifications(
            service_key=SERVICE_KEY,
            service_version=version,
            user_id=user_id,
            product_name=target_product,
        )
        assert service_specs == ServiceSpecificationsGet.model_validate(version_speced[0].model_dump()), (
            f"specifications for {version=} are not passed "
            f"down from {sorted_versions[INDEX_FIRST_SERVICE_VERSION_WITH_SPEC]}"
        )

    # check version from second to last use the second version
    for version in sorted_versions[INDEX_SECOND_SERVICE_VERSION_WITH_SPEC:]:
        service_specs = await get_service_specifications(
            service_key=SERVICE_KEY,
            service_version=version,
            user_id=user_id,
            product_name=target_product,
        )
        assert service_specs == ServiceSpecificationsGet.model_validate(version_speced[1].model_dump()), (
            f"specifications for {version=} are not passed "
            f"down from {sorted_versions[INDEX_SECOND_SERVICE_VERSION_WITH_SPEC]}"
        )


async def test_service_specifications_are_isolated_by_product(
    background_task_lifespan_disabled,
    mocked_director_rest_api: respx.MockRouter,
    rabbitmq_and_rpc_setup_disabled: None,
    repository_lifespan_disabled: None,
    get_service_specifications: Callable[..., Awaitable[ServiceSpecificationsGet]],
    default_service_specifications: ServiceSpecifications,
    user_id: UserID,
    user: dict[str, Any],
    user_groups_ids: list[int],
    target_product: ProductName,
    other_product: ProductName,
    create_fake_service_data: CreateFakeServiceDataCallable,
    services_db_tables_injector: Callable,
    services_specifications_injector: Callable,
    create_service_specifications: Callable[..., ServiceSpecificationsAtDB],
):
    """Specs defined for product A must NOT be returned when querying product B."""
    SERVICE_KEY = "simcore/services/dynamic/jupyterlab"
    SERVICE_VERSION = "0.0.1"

    # register service in both products
    for product in (target_product, other_product):
        await services_db_tables_injector(
            [
                create_fake_service_data(
                    SERVICE_KEY,
                    SERVICE_VERSION,
                    team_access=None,
                    everyone_access=None,
                    product=product,
                )
            ]
        )

    everyone_gid, _user_gid, _team_gid = user_groups_ids

    async def _get(product_name: ProductName) -> ServiceSpecificationsGet:
        return await get_service_specifications(
            service_key=SERVICE_KEY,
            service_version=SERVICE_VERSION,
            user_id=user_id,
            product_name=product_name,
        )

    # inject specs ONLY for target_product
    target_specs = create_service_specifications(SERVICE_KEY, SERVICE_VERSION, everyone_gid, target_product)
    await services_specifications_injector(target_specs)

    # querying target_product should return the injected specs
    assert await _get(target_product) == ServiceSpecificationsGet.model_validate(target_specs.model_dump())

    # querying other_product should return DEFAULT specs (not the ones from target_product)
    assert (await _get(other_product)).model_dump() == default_service_specifications.model_dump()

    # now inject different specs for other_product
    other_specs = create_service_specifications(SERVICE_KEY, SERVICE_VERSION, everyone_gid, other_product)
    await services_specifications_injector(other_specs)

    # each product returns its own specs
    target_result = await _get(target_product)
    other_result = await _get(other_product)
    assert target_result == ServiceSpecificationsGet.model_validate(target_specs.model_dump())
    assert other_result == ServiceSpecificationsGet.model_validate(other_specs.model_dump())

    # the two products have different specs
    assert target_result != other_result
