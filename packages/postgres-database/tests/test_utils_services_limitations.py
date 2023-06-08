from aiopg.sa.connection import SAConnection
from simcore_postgres_database.utils_services_limitations import ServicesLimitationsRepo


async def test_create_service_limitation(connection: SAConnection):
    repo = ServicesLimitationsRepo()
    # create an entry with everything set to None
    created_limit = await repo.create(
        connection, gid=1, cluster_id=None, ram=None, cpu=None, vram=None, gpu=None
    )
    assert created_limit
    assert created_limit.gid == 1
    assert created_limit.cluster_id is None
    assert created_limit.ram is None
    assert created_limit.cpu is None
    assert created_limit.vram is None
    assert created_limit.gpu is None
    assert created_limit.created == created_limit.modified


async def test_modified_timestamp_auto_updates_with_changes(
    connection: SAConnection,
):
    ...


async def test_get_group_services_limitations_correctly_merges():
    ...


async def test_multiple_same_group_limitations_on_same_cluster_fail():
    ...


async def test_multiple_same_group_limitations_on_different_clusters_succeed():
    ...
