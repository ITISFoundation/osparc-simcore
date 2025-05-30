# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import Callable
from typing import Any, Protocol

import pytest
import simcore_service_catalog.service.access_rights
from fastapi import FastAPI
from models_library.groups import GroupID
from models_library.products import ProductName
from models_library.services import ServiceMetaDataPublished, ServiceVersion
from models_library.services_authoring import Author
from pydantic import TypeAdapter
from pytest_mock import MockerFixture
from pytest_simcore.helpers.catalog_services import CreateFakeServiceDataCallable
from simcore_service_catalog.models.services_db import ServiceAccessRightsDB
from simcore_service_catalog.repository.services import ServicesRepository
from simcore_service_catalog.service.access_rights import (
    evaluate_default_service_ownership_and_rights,
    inherit_from_latest_compatible_release,
    reduce_access_rights,
)
from sqlalchemy.ext.asyncio import AsyncEngine

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture
def new_service_metadata_published(user: dict[str, Any]) -> ServiceMetaDataPublished:
    MOST_UPDATED_EXAMPLE = -1
    metadata = ServiceMetaDataPublished.model_validate(
        ServiceMetaDataPublished.model_json_schema()["examples"][MOST_UPDATED_EXAMPLE]
    )
    metadata.contact = user["email"]
    metadata.authors = [
        Author(name=user["name"], email=user["email"], affiliation=None)
    ]
    metadata.version = TypeAdapter(ServiceVersion).validate_python("1.0.11")
    # Set all inheritable fields to None initially
    metadata.icon = None
    metadata.thumbnail = None
    return metadata


@pytest.fixture
def app_with_repo(
    sqlalchemy_async_engine: AsyncEngine,
    target_product: ProductName,
    mocker: MockerFixture,
) -> tuple[FastAPI, ServicesRepository]:
    """Creates FastAPI app with services repository setup."""
    app = FastAPI()
    app.state.engine = sqlalchemy_async_engine
    app.state.settings = mocker.Mock()
    app.state.default_product_name = target_product

    services_repo = ServicesRepository(app.state.engine)
    return app, services_repo


class CreateLatetReleaseCallable(Protocol):
    """Callable to create a latest release with specified metadata fields."""

    async def __call__(self, metadata_fields: dict[str, Any]) -> dict[str, Any]: ...


@pytest.fixture
def create_latest_release(
    create_fake_service_data: CreateFakeServiceDataCallable,
    new_service_metadata_published: ServiceMetaDataPublished,
    target_product: ProductName,
    services_db_tables_injector: Callable,
) -> CreateLatetReleaseCallable:
    """Creates a latest release with specified metadata fields."""

    from packaging.version import Version

    new_version = Version(new_service_metadata_published.version)

    async def _create(metadata_fields: dict[str, Any]) -> dict[str, Any]:
        latest_release_service, *latest_release_service_access_rights = (
            create_fake_service_data(
                new_service_metadata_published.key,
                f"{new_version.major}.{new_version.minor}.{new_version.micro-1}",
                team_access="x",
                everyone_access=None,
                product=target_product,
            )
        )

        # Update with provided metadata fields
        for field, value in metadata_fields.items():
            latest_release_service[field] = value

        latest_release = (latest_release_service, *latest_release_service_access_rights)
        await services_db_tables_injector([latest_release])
        return latest_release_service

    return _create


def test_reduce_access_rights():
    sample = ServiceAccessRightsDB.model_validate(
        {
            "key": "simcore/services/dynamic/sim4life",
            "version": "1.0.9",
            "gid": 8,
            "execute_access": True,
            "write_access": True,
            "product_name": "osparc",
        }
    )

    # fixture with overrides and with other products
    reduced = reduce_access_rights(
        [
            sample.model_copy(deep=True),
            sample.model_copy(deep=True),
            sample.model_copy(update={"execute_access": False}, deep=True),
            sample.model_copy(update={"product_name": "s4l"}, deep=True),
        ]
    )

    # two products with the same flags
    assert len(reduced) == 2
    assert reduced[0].model_dump(include={"execute_access", "write_access"}) == {
        "execute_access": True,
        "write_access": True,
    }
    assert reduced[1].model_dump(include={"execute_access", "write_access"}) == {
        "execute_access": True,
        "write_access": True,
    }

    # two gids with the different falgs
    reduced = reduce_access_rights(
        [
            sample.model_copy(deep=True),
            sample.model_copy(
                update={"gid": 1, "execute_access": True, "write_access": False},
                deep=True,
            ),
        ]
    )

    assert len(reduced) == 2
    assert reduced[0].model_dump(include={"execute_access", "write_access"}) == {
        "execute_access": True,
        "write_access": True,
    }
    assert reduced[1].model_dump(include={"execute_access", "write_access"}) == {
        "execute_access": True,
        "write_access": False,
    }


async def test_metadata_inheritance_variations(
    new_service_metadata_published: ServiceMetaDataPublished,
    app_with_repo: tuple[FastAPI, ServicesRepository],
    create_latest_release: CreateLatetReleaseCallable,
):
    """Test different variations of metadata inheritance with complete previous release."""
    app, services_repo = app_with_repo

    # Set up a previous release with all metadata fields
    latest_release_service = await create_latest_release(
        {
            "icon": "https://foo/previous_icon.svg",
            "thumbnail": "https://foo/previous_thumbnail.jpg",
        }
    )

    # Case 1: All fields missing in new service - only icon and thumbnail should be inherited
    new_service = new_service_metadata_published.model_copy(deep=True)
    inherited_data = await inherit_from_latest_compatible_release(
        services_repo, service_metadata=new_service
    )

    assert inherited_data["metadata_updates"] == {
        "icon": latest_release_service["icon"],
        "thumbnail": latest_release_service["thumbnail"],
    }

    # Case 2: Some fields present, others missing
    new_service = new_service_metadata_published.model_copy(
        deep=True,
        update={
            "thumbnail": None,  # Missing field
            "icon": "https://foo/new_icon.svg",
        },
    )

    inherited_data = await inherit_from_latest_compatible_release(
        services_repo, service_metadata=new_service
    )

    # Only thumbnail should be inherited
    assert "icon" not in inherited_data["metadata_updates"]
    assert inherited_data["metadata_updates"] == {
        "thumbnail": latest_release_service["thumbnail"],
    }

    # Case 3: All fields present in new service - nothing should be inherited
    new_service = new_service_metadata_published.model_copy(
        deep=True,
        update={
            "icon": "https://foo/new_icon.svg",
            "thumbnail": "https://foo/new_thumbnail.jpg",
        },
    )

    inherited_data = await inherit_from_latest_compatible_release(
        services_repo, service_metadata=new_service
    )

    # No metadata should be inherited
    assert inherited_data["metadata_updates"] == {}


async def test_metadata_inheritance_with_incomplete_previous_release(
    new_service_metadata_published: ServiceMetaDataPublished,
    app_with_repo: tuple[FastAPI, ServicesRepository],
    create_latest_release: CreateLatetReleaseCallable,
):
    """Test metadata inheritance when previous release has incomplete metadata fields."""
    app, services_repo = app_with_repo

    # Case 4: Previous release missing some fields
    latest_release_service = await create_latest_release(
        {
            "icon": "https://foo/previous_icon.svg",
            "thumbnail": "https://foo/previous_thumbnail.jpg",
        }
    )

    new_service = new_service_metadata_published.model_copy(deep=True)
    inherited_data = await inherit_from_latest_compatible_release(
        services_repo, service_metadata=new_service
    )

    # Only icon and thumbnail should be inherited
    assert inherited_data["metadata_updates"] == {
        "icon": latest_release_service["icon"],
        "thumbnail": latest_release_service["thumbnail"],
    }
    assert "description" not in inherited_data["metadata_updates"]


async def test_service_upgrade_metadata_inheritance_old_service(
    user_groups_ids: list[GroupID],
    target_product: ProductName,
    mocker: MockerFixture,
    new_service_metadata_published: ServiceMetaDataPublished,
    app_with_repo: tuple[FastAPI, ServicesRepository],
    create_latest_release: CreateLatetReleaseCallable,
):
    """Test inheritance behavior when the service is considered old"""
    everyone_gid, user_gid, team_gid = user_groups_ids
    app, services_repo = app_with_repo

    # Mock to make the service appear as old
    mocker.patch.object(
        simcore_service_catalog.service.access_rights,
        "_is_old_service",
        return_value=True,
    )

    # Create latest-release service for testing inheritance with all metadata fields
    latest_release_service = await create_latest_release(
        {
            "icon": "https://foo/previous_icon.svg",
            "description": "Previous description",  # This won't be inherited
            "thumbnail": "https://foo/previous_thumbnail.jpg",
        }
    )

    # DEFAULT policies for old service
    owner_gid, service_access_rights = (
        await evaluate_default_service_ownership_and_rights(
            app, service=new_service_metadata_published, product_name=target_product
        )
    )

    # For old services, everyone should have access
    assert owner_gid == user_gid
    assert len(service_access_rights) == 2  # Owner + everyone
    assert {a.gid for a in service_access_rights} == {owner_gid, everyone_gid}

    # Check owner access
    owner_access = next(a for a in service_access_rights if a.gid == owner_gid)
    assert owner_access.model_dump(include={"execute_access", "write_access"}) == {
        "execute_access": True,
        "write_access": True,
    }

    # Check everyone access
    everyone_access = next(a for a in service_access_rights if a.gid == everyone_gid)
    assert everyone_access.model_dump(include={"execute_access", "write_access"}) == {
        "execute_access": True,
        "write_access": False,  # Everyone can execute but not modify
    }

    # Inheritance policy (both access rights and metadata)
    inherited_data = await inherit_from_latest_compatible_release(
        services_repo, service_metadata=new_service_metadata_published
    )

    # Check metadata inheritance - only icon and thumbnail should be inherited
    inherited_metadata = inherited_data["metadata_updates"]
    assert "description" not in inherited_metadata
    assert inherited_metadata == {
        "icon": latest_release_service["icon"],
        "thumbnail": latest_release_service["thumbnail"],
    }


async def test_service_upgrade_metadata_inheritance_new_service_multi_product(
    user_groups_ids: list[GroupID],
    target_product: ProductName,
    other_product: ProductName,
    services_db_tables_injector: Callable,
    create_fake_service_data: CreateFakeServiceDataCallable,
    mocker: MockerFixture,
    new_service_metadata_published: ServiceMetaDataPublished,
    app_with_repo: tuple[FastAPI, ServicesRepository],
):
    """Test inheritance behavior when the service is new and latest version exists in multiple products"""
    everyone_gid, user_gid, team_gid = user_groups_ids
    app, services_repo = app_with_repo

    # Avoids calls to director API - service is new
    mocker.patch.object(
        simcore_service_catalog.service.access_rights,
        "_is_old_service",
        return_value=False,
    )

    # Create latest-release service
    latest_release_service, *latest_release_service_access_rights = (
        create_fake_service_data(
            new_service_metadata_published.key,
            "1.0.10",
            team_access="x",
            everyone_access=None,
            product=target_product,
        )
    )

    latest_release_service["icon"] = "https://foo/previous_icon.svg"
    latest_release = (latest_release_service, *latest_release_service_access_rights)

    # latest-release in other product
    _, *latest_release_service_access_rights_in_other_product = (
        create_fake_service_data(
            new_service_metadata_published.key,
            latest_release_service["version"],
            team_access="x",
            everyone_access=None,
            product=other_product,  # <-- different product
        )
    )

    latest_release_in_other_product = (
        latest_release_service,
        *latest_release_service_access_rights_in_other_product,  # <-- different product
    )

    # Setup multiple versions in database
    await services_db_tables_injector(
        [
            create_fake_service_data(
                new_service_metadata_published.key,
                "1.0.1",
                team_access=None,
                everyone_access=None,
                product=target_product,
            ),
            create_fake_service_data(
                new_service_metadata_published.key,
                "1.0.9",
                team_access=None,
                everyone_access=None,
                product=target_product,
            ),
            latest_release,
            latest_release_in_other_product,
        ]
    )

    # DEFAULT policies
    owner_gid, service_access_rights = (
        await evaluate_default_service_ownership_and_rights(
            app, service=new_service_metadata_published, product_name=target_product
        )
    )
    assert owner_gid == user_gid
    assert len(service_access_rights) == 1  # Only owner for new service
    assert {a.gid for a in service_access_rights} == {owner_gid}
    assert service_access_rights[0].model_dump() == {
        "key": new_service_metadata_published.key,
        "version": new_service_metadata_published.version,
        "gid": user_gid,
        "product_name": target_product,
        "execute_access": True,
        "write_access": True,
    }
    assert service_access_rights[0].product_name == target_product

    # Inheritance policy (both access rights and metadata)
    inherited_data = await inherit_from_latest_compatible_release(
        services_repo, service_metadata=new_service_metadata_published
    )

    # Check access rights inheritance
    inherited_access_rights = inherited_data["access_rights"]
    assert len(inherited_access_rights) == 4
    assert {a.gid for a in inherited_access_rights} == {team_gid, owner_gid}
    assert {a.product_name for a in inherited_access_rights} == {
        target_product,
        other_product,
    }

    # Check metadata inheritance
    inherited_metadata = inherited_data["metadata_updates"]
    assert "icon" in inherited_metadata
    assert inherited_metadata["icon"] == latest_release_service["icon"]

    # ALL
    service_access_rights += inherited_access_rights
    service_access_rights = reduce_access_rights(service_access_rights)

    assert len(service_access_rights) == 4
    assert {a.gid for a in service_access_rights} == {
        team_gid,
        owner_gid,
    }, "last version was exposed to a team"
    assert {a.product_name for a in service_access_rights} == {
        target_product,
        other_product,
    }, "last version was exposed to two products"
