# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import AsyncIterator

import pytest
from pytest_simcore.helpers.faker_factories import (
    random_service_consume_filetype,
    random_service_meta_data,
)
from pytest_simcore.helpers.postgres_tools import insert_and_get_row_lifespan
from simcore_postgres_database.models.services import services_meta_data
from simcore_postgres_database.models.services_consume_filetypes import (
    services_consume_filetypes,
)
from simcore_service_webserver.studies_dispatcher._models import ViewerInfo
from simcore_service_webserver.studies_dispatcher._repository import (
    StudiesDispatcherRepository,
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
async def consume_filetypes_in_db(
    asyncpg_engine: AsyncEngine, service_metadata_in_db: dict
):
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
def studies_dispatcher_repository(
    asyncpg_engine: AsyncEngine,
) -> StudiesDispatcherRepository:
    """Create StudiesDispatcherRepository instance."""
    return StudiesDispatcherRepository(engine=asyncpg_engine)


async def test_list_viewers_info_all(
    studies_dispatcher_repository: StudiesDispatcherRepository,
    consume_filetypes_in_db: dict,
):
    """Test listing all viewer services."""
    # Act
    viewers = await studies_dispatcher_repository.list_viewers_info()

    # Assert
    assert len(viewers) == 1
    viewer = viewers[0]
    assert isinstance(viewer, ViewerInfo)
    assert viewer.key == consume_filetypes_in_db["service_key"]
    assert viewer.version == consume_filetypes_in_db["service_version"]
    assert viewer.filetype == consume_filetypes_in_db["filetype"]
    assert viewer.label == consume_filetypes_in_db["service_display_name"]
    assert viewer.input_port_key == consume_filetypes_in_db["service_input_port"]
    assert viewer.is_guest_allowed == consume_filetypes_in_db["is_guest_allowed"]


async def test_list_viewers_info_filtered_by_filetype(
    studies_dispatcher_repository: StudiesDispatcherRepository,
    consume_filetypes_in_db: dict,
):
    """Test listing viewer services filtered by file type."""
    # Act
    viewers = await studies_dispatcher_repository.list_viewers_info(file_type="CSV")

    # Assert
    assert len(viewers) == 1
    assert viewers[0].filetype == "CSV"

    # Test with non-existent filetype
    viewers_empty = await studies_dispatcher_repository.list_viewers_info(
        file_type="NONEXISTENT"
    )
    assert len(viewers_empty) == 0


async def test_list_viewers_info_only_default(
    studies_dispatcher_repository: StudiesDispatcherRepository,
    consume_filetypes_in_db: dict,
):
    """Test listing only default viewer services."""
    # Act
    viewers = await studies_dispatcher_repository.list_viewers_info(
        file_type="CSV", only_default=True
    )

    # Assert
    assert len(viewers) == 1
    assert viewers[0].filetype == "CSV"
