# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from models_library.services import ServiceKey, ServiceVersion
from simcore_service_webserver.studies_dispatcher._catalog import (
    ServiceMetaData,
    ValidService,
    iter_latest_product_services,
    validate_requested_service,
)
from simcore_service_webserver.studies_dispatcher._errors import ServiceNotFoundError
from simcore_service_webserver.studies_dispatcher.settings import (
    StudiesDispatcherSettings,
)
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
def studies_dispatcher_settings() -> StudiesDispatcherSettings:
    return StudiesDispatcherSettings(
        STUDIES_DEFAULT_SERVICE_THUMBNAIL="https://example.com/default-thumbnail.png"
    )


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
