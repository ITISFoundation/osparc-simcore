# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import pytest
from simcore_service_webserver.studies_dispatcher._models import ViewerInfo
from simcore_service_webserver.studies_dispatcher._repository import (
    StudiesDispatcherRepository,
)
from sqlalchemy.ext.asyncio import AsyncEngine


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
    viewers_empty = await studies_dispatcher_repository.list_viewers_info(file_type="NONEXISTENT")
    assert len(viewers_empty) == 0


async def test_list_viewers_info_only_default(
    studies_dispatcher_repository: StudiesDispatcherRepository,
    consume_filetypes_in_db: dict,
):
    """Test listing only default viewer services."""
    # Act
    viewers = await studies_dispatcher_repository.list_viewers_info(file_type="CSV", only_default=True)

    # Assert
    assert len(viewers) == 1
    assert viewers[0].filetype == "CSV"


async def test_get_default_viewer_for_filetype(
    studies_dispatcher_repository: StudiesDispatcherRepository,
    consume_filetypes_in_db: dict,
):
    """Test getting the default viewer for a specific file type."""
    # Act
    viewer = await studies_dispatcher_repository.get_default_viewer_for_filetype(file_type="CSV")

    # Assert
    assert viewer is not None
    assert isinstance(viewer, ViewerInfo)
    assert viewer.key == consume_filetypes_in_db["service_key"]
    assert viewer.version == consume_filetypes_in_db["service_version"]
    assert viewer.filetype == "CSV"
    assert viewer.label == consume_filetypes_in_db["service_display_name"]

    # Test with non-existent filetype
    viewer_none = await studies_dispatcher_repository.get_default_viewer_for_filetype(file_type="NONEXISTENT")
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
