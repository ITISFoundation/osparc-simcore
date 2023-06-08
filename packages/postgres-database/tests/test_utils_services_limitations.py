from dataclasses import fields

import pytest
from aiopg.sa.connection import SAConnection
from simcore_postgres_database.utils_services_limitations import (
    ServiceLimitationsCreate,
    ServiceLimitationsOperationNotAllowed,
    ServicesLimitationsRepo,
)


async def test_create_service_limitation(connection: SAConnection):
    repo = ServicesLimitationsRepo()
    input_limit = ServiceLimitationsCreate(
        gid=1, cluster_id=None, ram=None, cpu=None, vram=None, gpu=None
    )
    created_limit = await repo.create(connection, new_limits=input_limit)
    assert created_limit
    for field in fields(ServiceLimitationsCreate):
        assert getattr(created_limit, field.name) == getattr(input_limit, field.name)
    assert created_limit.created == created_limit.modified


async def test_multiple_same_group_limitations_on_same_cluster_fail(
    connection: SAConnection,
):
    repo = ServicesLimitationsRepo()
    input_limit = ServiceLimitationsCreate(
        gid=1, cluster_id=None, ram=None, cpu=None, vram=None, gpu=None
    )
    created_limit = await repo.create(connection, new_limits=input_limit)
    assert created_limit

    # doing it again shall raise
    with pytest.raises(ServiceLimitationsOperationNotAllowed):
        await repo.create(connection, new_limits=input_limit)


async def test_modified_timestamp_auto_updates_with_changes(
    connection: SAConnection,
):
    ...


async def test_get_group_services_limitations_correctly_merges():
    ...


async def test_multiple_same_group_limitations_on_different_clusters_succeed():
    ...
