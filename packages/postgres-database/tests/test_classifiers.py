# pylint: disable=no-value-for-parameter
# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

import json
from pathlib import Path

import psycopg2.errors
import pytest
import sqlalchemy as sa
from aiopg.sa.engine import Engine
from pytest_simcore.helpers.rawdata_fakers import random_group
from simcore_postgres_database.models.classifiers import group_classifiers
from simcore_postgres_database.models.groups import groups
from sqlalchemy import func, literal_column


@pytest.fixture
def web_client_resource_folder(osparc_simcore_root_dir: Path) -> Path:
    wcrf_path = (
        osparc_simcore_root_dir
        / "services"
        / "static-webserver"
        / "client"
        / "source"
        / "resource"
    )
    assert wcrf_path.exists()
    return wcrf_path


@pytest.fixture
def classifiers_bundle(web_client_resource_folder: Path) -> dict:
    bundle_path = web_client_resource_folder / "dev" / "classifiers.json"
    assert bundle_path.exists()
    return json.loads(bundle_path.read_text())


async def test_operations_on_group_classifiers(
    pg_engine: Engine, classifiers_bundle: dict
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

        assert row
        assert row[group_classifiers.c.gid] == gid
        assert row[group_classifiers.c.bundle] == classifiers_bundle

        # get bundle in one query
        bundle = await conn.scalar(
            sa.select(group_classifiers.c.bundle).where(group_classifiers.c.gid == gid)
        )
        assert bundle
        assert classifiers_bundle == bundle

        # Cannot add more than one classifier's bundle to the same group
        # pylint: disable=no-member
        with pytest.raises(psycopg2.errors.UniqueViolation):
            await conn.execute(group_classifiers.insert().values(bundle={}, gid=gid))

        # deleting a group deletes the classifier
        await conn.execute(groups.delete().where(groups.c.gid == gid))

        groups_count = await conn.scalar(sa.select(func.count(groups.c.gid)))
        classifiers_count = await conn.scalar(
            sa.select(func.count()).select_from(group_classifiers)
        )

        assert (
            groups_count == 1
        ), "There should be only the Everyone group in the database!"
        assert isinstance(classifiers_count, int)
        assert isinstance(groups_count, int)
        assert classifiers_count <= groups_count
        assert classifiers_count == 0

        # no bundle
        bundle = await conn.scalar(
            sa.select(group_classifiers.c.bundle).where(group_classifiers.c.gid == gid)
        )
        assert bundle is None
