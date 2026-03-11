# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable
# pylint: disable=too-many-arguments

import pytest
from models_library.groups import EVERYONE_GROUP_ID
from pytest_simcore.helpers.faker_factories import random_group_classifier
from pytest_simcore.helpers.postgres_tools import insert_and_get_row_lifespan
from simcore_postgres_database.models.classifiers import group_classifiers
from simcore_service_webserver.groups._classifiers_repository import (
    GroupClassifierRepository,
)
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
async def group_classifier_in_db(asyncpg_engine: AsyncEngine):
    """Pre-populate group_classifiers table with test data."""
    data = random_group_classifier(gid=EVERYONE_GROUP_ID)

    # pylint: disable=contextmanager-generator-missing-cleanup
    # NOTE: this code is safe since `@asynccontextmanager` takes care of the cleanup
    async with insert_and_get_row_lifespan(
        asyncpg_engine,
        table=group_classifiers,
        values=data,
        pk_col=group_classifiers.c.id,
        pk_value=data.get("id"),
    ) as row:
        yield row


@pytest.fixture
def group_classifier_repository(
    asyncpg_engine: AsyncEngine,
) -> GroupClassifierRepository:
    """Create GroupClassifierRepository instance."""
    return GroupClassifierRepository(engine=asyncpg_engine)


async def test_get_classifiers_from_bundle_returns_bundle(
    group_classifier_repository: GroupClassifierRepository,
    group_classifier_in_db: dict,
):
    """Test get_classifiers_from_bundle returns the stored bundle."""
    # Act
    bundle = await group_classifier_repository.get_classifiers_from_bundle(gid=group_classifier_in_db["gid"])

    # Assert
    assert bundle is not None
    assert bundle["vcs_url"] == "https://organization.classifiers.git"
    assert "classifiers" in bundle
    assert "project::dak" in bundle["classifiers"]
    assert bundle["classifiers"]["project::dak"]["display_name"] == "DAK"


async def test_group_uses_scicrunch_returns_false(
    group_classifier_repository: GroupClassifierRepository,
    group_classifier_in_db: dict,
):
    """Test group_uses_scicrunch returns False for non-scicrunch group."""
    # Act
    uses_scicrunch = await group_classifier_repository.group_uses_scicrunch(gid=group_classifier_in_db["gid"])

    # Assert
    assert uses_scicrunch is False


async def test_get_classifiers_from_bundle_returns_none_for_missing_gid(
    group_classifier_repository: GroupClassifierRepository,
):
    """Test get_classifiers_from_bundle returns None for non-existent gid."""
    # Act
    bundle = await group_classifier_repository.get_classifiers_from_bundle(gid=999999)

    # Assert
    assert bundle is None


async def test_group_uses_scicrunch_returns_false_for_missing_gid(
    group_classifier_repository: GroupClassifierRepository,
):
    """Test group_uses_scicrunch returns False for non-existent gid."""
    # Act
    uses_scicrunch = await group_classifier_repository.group_uses_scicrunch(gid=999999)

    # Assert
    assert uses_scicrunch is False
