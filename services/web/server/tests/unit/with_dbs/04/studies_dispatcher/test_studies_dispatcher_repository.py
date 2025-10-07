# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import AsyncIterator

import pytest
from models_library.groups import EVERYONE_GROUP_ID
from models_library.services import ServiceKey, ServiceVersion
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
from simcore_service_webserver.studies_dispatcher._catalog import (
    ServiceMetaData,
    ValidService,
    iter_latest_product_services,
    validate_requested_service,
)
from simcore_service_webserver.studies_dispatcher._errors import ServiceNotFoundError
from simcore_service_webserver.studies_dispatcher._models import ViewerInfo
from simcore_service_webserver.studies_dispatcher._repository import (
    StudiesDispatcherRepository,
)
from simcore_service_webserver.studies_dispatcher.settings import (
    StudiesDispatcherSettings,
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
async def service_access_rights_in_db(
    asyncpg_engine: AsyncEngine, service_metadata_in_db: dict
):
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


@pytest.fixture
def studies_dispatcher_settings() -> StudiesDispatcherSettings:
    return StudiesDispatcherSettings(
        STUDIES_DEFAULT_SERVICE_THUMBNAIL="https://example.com/default-thumbnail.png"
    )


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


async def test_get_default_viewer_for_filetype(
    studies_dispatcher_repository: StudiesDispatcherRepository,
    consume_filetypes_in_db: dict,
):
    """Test getting the default viewer for a specific file type."""
    # Act
    viewer = await studies_dispatcher_repository.get_default_viewer_for_filetype(
        file_type="CSV"
    )

    # Assert
    assert viewer is not None
    assert isinstance(viewer, ViewerInfo)
    assert viewer.key == consume_filetypes_in_db["service_key"]
    assert viewer.version == consume_filetypes_in_db["service_version"]
    assert viewer.filetype == "CSV"
    assert viewer.label == consume_filetypes_in_db["service_display_name"]

    # Test with non-existent filetype
    viewer_none = await studies_dispatcher_repository.get_default_viewer_for_filetype(
        file_type="NONEXISTENT"
    )
    assert viewer_none is None


async def test_find_compatible_viewer_found(
    studies_dispatcher_repository: StudiesDispatcherRepository,
    consume_filetypes_in_db: dict,
):
    """Test finding a compatible viewer service that exists."""
    # Act
    viewer = await studies_dispatcher_repository.find_compatible_viewer(
        file_type="CSV",
        service_key=consume_filetypes_in_db["service_key"],
        service_version="1.0.0",
    )

    # Assert
    assert viewer is not None
    assert isinstance(viewer, ViewerInfo)
    assert viewer.key == consume_filetypes_in_db["service_key"]
    assert viewer.version == "1.0.0"  # Should use the requested version
    assert viewer.filetype == "CSV"
    assert viewer.label == consume_filetypes_in_db["service_display_name"]


async def test_find_compatible_viewer_not_found(
    studies_dispatcher_repository: StudiesDispatcherRepository,
    consume_filetypes_in_db: dict,
):
    """Test finding a compatible viewer service that doesn't exist."""
    # Act - test with non-existent service key
    viewer = await studies_dispatcher_repository.find_compatible_viewer(
        file_type="CSV",
        service_key="simcore/services/dynamic/nonexistent",
        service_version="1.0.0",
    )

    # Assert
    assert viewer is None

    # Act - test with incompatible filetype
    viewer_wrong_filetype = await studies_dispatcher_repository.find_compatible_viewer(
        file_type="NONEXISTENT",
        service_key=consume_filetypes_in_db["service_key"],
        service_version="1.0.0",
    )

    # Assert
    assert viewer_wrong_filetype is None


async def test_iter_latest_product_services(
    asyncpg_engine: AsyncEngine,
    studies_dispatcher_settings: StudiesDispatcherSettings,
    service_metadata_in_db: dict,
    service_access_rights_in_db: dict,
    consume_filetypes_in_db: dict,
):
    """Test iterating through latest product services."""
    # Act
    services = []
    async for service in iter_latest_product_services(
        studies_dispatcher_settings, asyncpg_engine, product_name="osparc"
    ):
        services.append(service)

    # Assert
    assert len(services) == 1
    service = services[0]
    assert isinstance(service, ServiceMetaData)
    assert service.key == service_metadata_in_db["key"]
    assert service.version == service_metadata_in_db["version"]
    assert service.title == service_metadata_in_db["name"]
    assert service.description == service_metadata_in_db["description"]
    assert service.file_extensions == [consume_filetypes_in_db["filetype"]]


async def test_iter_latest_product_services_with_pagination(
    asyncpg_engine: AsyncEngine,
    studies_dispatcher_settings: StudiesDispatcherSettings,
    service_metadata_in_db: dict,
    service_access_rights_in_db: dict,
):
    """Test iterating through services with pagination."""
    # Act
    services = []
    async for service in iter_latest_product_services(
        studies_dispatcher_settings,
        asyncpg_engine,
        product_name="osparc",
        page_number=1,
        page_size=1,
    ):
        services.append(service)

    # Assert
    assert len(services) == 1


async def test_validate_requested_service_success(
    asyncpg_engine: AsyncEngine,
    service_metadata_in_db: dict,
    consume_filetypes_in_db: dict,
):
    """Test validating a service that exists and is valid."""
    # Act
    valid_service = await validate_requested_service(
        engine=asyncpg_engine,
        service_key=ServiceKey(service_metadata_in_db["key"]),
        service_version=ServiceVersion(service_metadata_in_db["version"]),
    )

    # Assert
    assert isinstance(valid_service, ValidService)
    assert valid_service.key == service_metadata_in_db["key"]
    assert valid_service.version == service_metadata_in_db["version"]
    assert valid_service.title == service_metadata_in_db["name"]
    assert valid_service.is_public == consume_filetypes_in_db["is_guest_allowed"]
    assert str(valid_service.thumbnail) == str(service_metadata_in_db["thumbnail"])


async def test_validate_requested_service_not_found(
    asyncpg_engine: AsyncEngine,
):
    """Test validating a service that doesn't exist."""
    # Act & Assert
    with pytest.raises(ServiceNotFoundError) as exc_info:
        await validate_requested_service(
            asyncpg_engine,
            service_key=ServiceKey("simcore/services/dynamic/nonexistent"),
            service_version=ServiceVersion("1.0.0"),
        )

    assert exc_info.value.service_key == "simcore/services/dynamic/nonexistent"
    assert exc_info.value.service_version == "1.0.0"
