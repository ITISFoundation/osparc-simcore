# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import AsyncIterator

import pytest
from models_library.groups import EVERYONE_GROUP_ID
from pytest_simcore.helpers.faker_factories import (
    random_service_access_rights,
    random_service_consume_filetype,
    random_service_meta_data,
)
from pytest_simcore.helpers.postgres_tools import insert_and_get_row_lifespan
from simcore_postgres_database.models.services import (
    services_access_rights,
    services_meta_data,
)
from simcore_postgres_database.models.services_consume_filetypes import (
    services_consume_filetypes,
)
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
async def service_metadata_in_db(asyncpg_engine: AsyncEngine) -> AsyncIterator[dict]:
    """Pre-populate services metadata table with test data."""
    service_data = random_service_meta_data(
        key="simcore/services/dynamic/viewer",
        version="1.0.0",
        name="Test Viewer Service",
    )
    # pylint: disable=contextmanager-generator-missing-cleanup
    async with insert_and_get_row_lifespan(
        asyncpg_engine,
        table=services_meta_data,
        values=service_data,
        pk_col=services_meta_data.c.key,
        pk_value=service_data["key"],
    ) as row:
        yield row
        # cleanup happens automatically


@pytest.fixture
async def consume_filetypes_in_db(asyncpg_engine: AsyncEngine, service_metadata_in_db: dict):
    """Pre-populate services consume filetypes table with test data."""
    consume_data = random_service_consume_filetype(
        service_key=service_metadata_in_db["key"],
        service_version=service_metadata_in_db["version"],
        filetype="CSV",
        service_display_name="CSV Viewer",
        service_input_port="input_1",
        preference_order=1,
        is_guest_allowed=True,
    )

    # pylint: disable=contextmanager-generator-missing-cleanup
    async with insert_and_get_row_lifespan(
        asyncpg_engine,
        table=services_consume_filetypes,
        values=consume_data,
        pk_col=services_consume_filetypes.c.service_key,
        pk_value=consume_data["service_key"],
    ) as row:
        yield row


@pytest.fixture
async def service_access_rights_in_db(asyncpg_engine: AsyncEngine, service_metadata_in_db: dict):
    """Pre-populate services access rights table with test data."""
    access_data = random_service_access_rights(
        key=service_metadata_in_db["key"],
        version=service_metadata_in_db["version"],
        gid=EVERYONE_GROUP_ID,
        execute_access=True,
        product_name="osparc",
    )

    # pylint: disable=contextmanager-generator-missing-cleanup
    async with insert_and_get_row_lifespan(
        asyncpg_engine,
        table=services_access_rights,
        values=access_data,
        pk_col=services_access_rights.c.key,
        pk_value=access_data["key"],
    ) as row:
        yield row
