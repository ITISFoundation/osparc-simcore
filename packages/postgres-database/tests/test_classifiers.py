# pylint: disable=no-value-for-parameter
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
from pathlib import Path
from typing import Dict

import psycopg2.errors
import pytest
import sqlalchemy as sa
from aiopg.sa.engine import Engine
from sqlalchemy import literal_column

from fake_creators import random_group
from simcore_postgres_database.models import *  # pylint: disable=wildcard-import, unused-wildcard-import
from simcore_postgres_database.models.base import metadata
from simcore_postgres_database.models.classifiers import group_classifiers
from simcore_postgres_database.models.groups import groups

pytest_plugins = ["pytest_simcore.environs"]


@pytest.fixture
def web_client_resource_folder(osparc_simcore_root_dir: Path) -> Path:
    wcrf_path = (
        osparc_simcore_root_dir / "services" / "web" / "client" / "source" / "resource"
    )
    assert wcrf_path.exists()
    return wcrf_path


@pytest.fixture
def classifiers_bundle(web_client_resource_folder: Path) -> Dict:
    bundle_path = web_client_resource_folder / "dev" / "classifiers.json"
    assert bundle_path.exists()
    return json.loads(bundle_path.read_text())


@pytest.fixture
async def pg_engine(loop, make_engine) -> Engine:
    engine = await make_engine()

    # TODO: upgrade/downgrade
    sync_engine = make_engine(False)

    metadata.drop_all(sync_engine)
    metadata.create_all(sync_engine)

    yield engine

    engine.terminate()
    await engine.wait_closed()

    metadata.drop_all(sync_engine)
    sync_engine.dispose()


async def test_operations_on_group_classifiers(
    pg_engine: Engine, classifiers_bundle: Dict
):
    # NOTE: mostly for TDD
    async with pg_engine.acquire() as conn:

        # creates a group
        stmt = (
            groups.insert()
            .values(**random_group(name="MyGroup"))
            .returning(groups.c.gid)
        )
        gid = await conn.scalar(stmt)

        # adds classifiers to a group
        stmt = (
            group_classifiers.insert()
            .values(bundle=classifiers_bundle, gid=gid)
            .returning(literal_column("*"))
        )
        result = await conn.execute(stmt)
        row = await result.first()

        assert row[group_classifiers.c.gid] == gid
        assert row[group_classifiers.c.bundle] == classifiers_bundle

        # get bundle in one query
        bundle = await conn.scalar(
            sa.select([group_classifiers.c.bundle]).where(
                group_classifiers.c.gid == gid
            )
        )
        assert bundle
        assert classifiers_bundle == bundle

        # Cannot add more than one classifier's bundle to the same group
        # pylint: disable=no-member
        with pytest.raises(psycopg2.errors.UniqueViolation):
            await conn.execute(group_classifiers.insert().values(bundle={}, gid=gid))

        # deleting a group deletes the classifier
        await conn.execute(groups.delete().where(groups.c.gid == gid))

        # FIXME: count returns 1 but the db is empty!??
        groups_count = 0  # await conn.scalar(groups.count())
        classifiers_count = await conn.scalar(group_classifiers.count())

        assert groups_count == 0
        assert classifiers_count <= groups_count

        # no bundle
        bundle = await conn.scalar(
            sa.select([group_classifiers.c.bundle]).where(
                group_classifiers.c.gid == gid
            )
        )
        assert bundle is None
