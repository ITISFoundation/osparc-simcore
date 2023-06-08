# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments
from dataclasses import fields
from typing import Awaitable, Callable

import pytest
from aiopg.sa.connection import SAConnection
from aiopg.sa.result import RowProxy
from faker import Faker
from simcore_postgres_database.utils_services_limitations import (
    ServiceLimitationsCreate,
    ServiceLimitationsOperationNotAllowed,
    ServicesLimitationsRepo,
)


@pytest.fixture
def random_service_limitations(
    faker: Faker,
) -> Callable[[int, int | None], ServiceLimitationsCreate]:
    def _creator(gid: int, cluster_id: int | None) -> ServiceLimitationsCreate:
        return ServiceLimitationsCreate(
            gid=gid,
            cluster_id=cluster_id,
            ram=faker.pyint(),
            cpu=faker.pydecimal(),
            vram=faker.pyint(),
            gpu=faker.pyint(),
        )

    return _creator


async def test_create_service_limitation(
    connection: SAConnection,
    random_service_limitations: Callable[[int, int | None], ServiceLimitationsCreate],
):
    # NOTE: these test works because the everyone group (gid=1) exists
    repo = ServicesLimitationsRepo()
    input_limit = random_service_limitations(1, None)
    created_limit = await repo.create(connection, new_limits=input_limit)
    assert created_limit
    for field in fields(ServiceLimitationsCreate):
        assert getattr(created_limit, field.name) == getattr(input_limit, field.name)
    assert created_limit.created == created_limit.modified


async def test_multiple_same_group_limitations_on_same_cluster_fail(
    connection: SAConnection,
    random_service_limitations: Callable[[int, int | None], ServiceLimitationsCreate],
):
    # NOTE: these test works because the everyone group (gid=1) exists
    repo = ServicesLimitationsRepo()
    created_limit = await repo.create(
        connection, new_limits=random_service_limitations(1, None)
    )
    assert created_limit

    # doing it again shall raise
    with pytest.raises(ServiceLimitationsOperationNotAllowed):
        await repo.create(connection, new_limits=random_service_limitations(1, None))


async def test_multiple_same_group_limitations_on_different_clusters_succeed(
    connection: SAConnection,
    random_service_limitations: Callable[[int, int | None], ServiceLimitationsCreate],
    create_fake_cluster: Callable[..., Awaitable[int]],
):
    # NOTE: these test works because the everyone group (gid=1) exists
    repo = ServicesLimitationsRepo()
    created_limit = await repo.create(
        connection, new_limits=random_service_limitations(1, None)
    )
    assert created_limit

    cluster_id = await create_fake_cluster(owner=1)
    created_limit_on_other_cluster = await repo.create(
        connection, new_limits=random_service_limitations(1, cluster_id)
    )
    assert created_limit_on_other_cluster


async def test_multiple_same_group_limitations_on_same_cluster_different_groups_succeed(
    connection: SAConnection,
    random_service_limitations: Callable[[int, int | None], ServiceLimitationsCreate],
    create_fake_group: Callable[..., Awaitable[RowProxy]],
):
    # NOTE: these test works because the everyone group (gid=1) exists
    repo = ServicesLimitationsRepo()
    created_limit = await repo.create(
        connection, new_limits=random_service_limitations(1, None)
    )
    assert created_limit
    group = await create_fake_group(connection)
    created_limit_for_new_group = await repo.create(
        connection, new_limits=random_service_limitations(group.gid, None)
    )
    assert created_limit_for_new_group


async def test_modified_timestamp_auto_updates_with_changes(
    connection: SAConnection,
):
    ...


async def test_get_group_services_limitations_correctly_merges():
    ...
