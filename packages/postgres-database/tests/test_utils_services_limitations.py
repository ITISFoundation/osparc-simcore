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
    ServiceLimitationsOperationNotFound,
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
    input_limit = random_service_limitations(1, None)
    created_limit = await ServicesLimitationsRepo.create(
        connection, new_limits=input_limit
    )
    assert created_limit
    for field in fields(ServiceLimitationsCreate):
        assert getattr(created_limit, field.name) == getattr(input_limit, field.name)
    assert created_limit.created == created_limit.modified


async def test_multiple_same_group_limitations_on_same_cluster_fail(
    connection: SAConnection,
    random_service_limitations: Callable[[int, int | None], ServiceLimitationsCreate],
):
    # NOTE: these test works because the everyone group (gid=1) exists
    created_limit = await ServicesLimitationsRepo.create(
        connection, new_limits=random_service_limitations(1, None)
    )
    assert created_limit

    # doing it again shall raise
    with pytest.raises(ServiceLimitationsOperationNotAllowed):
        await ServicesLimitationsRepo.create(
            connection, new_limits=random_service_limitations(1, None)
        )


async def test_multiple_same_group_limitations_on_different_clusters_succeed(
    connection: SAConnection,
    random_service_limitations: Callable[[int, int | None], ServiceLimitationsCreate],
    create_fake_cluster: Callable[..., Awaitable[int]],
):
    # NOTE: these test works because the everyone group (gid=1) exists
    created_limit = await ServicesLimitationsRepo.create(
        connection, new_limits=random_service_limitations(1, None)
    )
    assert created_limit

    cluster_id = await create_fake_cluster(owner=1)
    created_limit_on_other_cluster = await ServicesLimitationsRepo.create(
        connection, new_limits=random_service_limitations(1, cluster_id)
    )
    assert created_limit_on_other_cluster


async def test_multiple_same_group_limitations_on_same_cluster_different_groups_succeed(
    connection: SAConnection,
    random_service_limitations: Callable[[int, int | None], ServiceLimitationsCreate],
    create_fake_group: Callable[..., Awaitable[RowProxy]],
):
    # NOTE: these test works because the everyone group (gid=1) exists
    created_limit = await ServicesLimitationsRepo.create(
        connection, new_limits=random_service_limitations(1, None)
    )
    assert created_limit
    group = await create_fake_group(connection)
    created_limit_for_new_group = await ServicesLimitationsRepo.create(
        connection, new_limits=random_service_limitations(group.gid, None)
    )
    assert created_limit_for_new_group


async def test_modified_timestamp_auto_updates_with_changes(
    connection: SAConnection,
    random_service_limitations: Callable[[int, int | None], ServiceLimitationsCreate],
):
    # NOTE: these test works because the everyone group (gid=1) exists
    created_limit = await ServicesLimitationsRepo.create(
        connection, new_limits=random_service_limitations(1, None)
    )
    assert created_limit
    assert created_limit.ram is not None
    # modify the limit
    updated_limit = await ServicesLimitationsRepo.update(
        connection, gid=1, cluster_id=None, ram=created_limit.ram + 25
    )
    assert updated_limit
    assert updated_limit.ram is not None
    assert created_limit.ram == (updated_limit.ram - 25)
    assert updated_limit.modified > created_limit.modified
    assert updated_limit.created == created_limit.created


async def test_update_services_limitations_raises_if_not_found(
    connection: SAConnection,
):
    # NOTE: these test works because the everyone group (gid=1) exists
    with pytest.raises(ServiceLimitationsOperationNotFound):
        await ServicesLimitationsRepo.update(connection, gid=1, cluster_id=None, ram=25)


async def test_get_services_limitations(
    connection: SAConnection,
    random_service_limitations: Callable[[int, int | None], ServiceLimitationsCreate],
):
    # NOTE: these test works because the everyone group (gid=1) exists
    created_limit = await ServicesLimitationsRepo.create(
        connection, new_limits=random_service_limitations(1, None)
    )
    assert created_limit

    received_limit = await ServicesLimitationsRepo.get(
        connection, gid=1, cluster_id=None
    )
    assert received_limit == created_limit


async def test_get_services_limitations_raises_if_not_found(
    connection: SAConnection,
):
    # NOTE: these test works because the everyone group (gid=1) exists
    with pytest.raises(ServiceLimitationsOperationNotFound):
        await ServicesLimitationsRepo.get(connection, gid=1, cluster_id=None)


async def test_delete_services_limitations(
    connection: SAConnection,
    random_service_limitations: Callable[[int, int | None], ServiceLimitationsCreate],
):
    # NOTE: these test works because the everyone group (gid=1) exists
    created_limit = await ServicesLimitationsRepo.create(
        connection, new_limits=random_service_limitations(1, None)
    )
    assert created_limit
    received_limit = await ServicesLimitationsRepo.get(
        connection, gid=1, cluster_id=None
    )
    assert received_limit == created_limit
    # now delete and verify
    await ServicesLimitationsRepo.delete(connection, gid=1, cluster_id=None)
    with pytest.raises(ServiceLimitationsOperationNotFound):
        await ServicesLimitationsRepo.get(connection, gid=1, cluster_id=None)


async def test_list_service_limitations_for_user(
    connection: SAConnection,
    create_fake_user: Callable[..., Awaitable[RowProxy]],
    create_fake_group: Callable[..., Awaitable[RowProxy]],
    random_service_limitations: Callable[[int, int | None], ServiceLimitationsCreate],
):
    group = await create_fake_group(connection)
    user = await create_fake_user(connection, group)
    repo = ServicesLimitationsRepo(user_id=user.id)
    list_limits = await repo.list_for_user(connection, cluster_id=None)
    assert list_limits is not None
    assert len(list_limits) == 0

    # NOTE: these test works because the everyone group (gid=1) exists
    # here we have now 1 service limits set for the group everyone
    everyone_limit = await ServicesLimitationsRepo.create(
        connection, new_limits=random_service_limitations(1, None)
    )
    assert everyone_limit
    list_limits = await repo.list_for_user(connection, cluster_id=None)
    assert list_limits is not None
    assert len(list_limits) == 1
    assert list_limits[0] == everyone_limit

    # add a limit on the group of the user
    group_limit = await ServicesLimitationsRepo.create(
        connection, new_limits=random_service_limitations(group.gid, None)
    )
    assert group_limit
    list_limits = await repo.list_for_user(connection, cluster_id=None)
    assert list_limits is not None
    assert len(list_limits) == 2
    assert all(limit in list_limits for limit in [everyone_limit, group_limit])

    # add a limit on the primary group
    user_limit = await ServicesLimitationsRepo.create(
        connection, new_limits=random_service_limitations(user.primary_gid, None)
    )
    assert user_limit
    list_limits = await repo.list_for_user(connection, cluster_id=None)
    assert list_limits is not None
    assert len(list_limits) == 3
    assert all(
        limit in list_limits for limit in [everyone_limit, group_limit, user_limit]
    )
