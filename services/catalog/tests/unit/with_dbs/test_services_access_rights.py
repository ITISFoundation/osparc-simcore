# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import Callable

from fastapi import FastAPI
from models_library.groups import GroupAtDB
from models_library.products import ProductName
from models_library.services import ServiceMetaDataPublished, ServiceVersion
from pydantic import TypeAdapter
from simcore_service_catalog.db.repositories.services import ServicesRepository
from simcore_service_catalog.models.services_db import ServiceAccessRightsAtDB
from simcore_service_catalog.services.access_rights import (
    evaluate_auto_upgrade_policy,
    evaluate_default_policy,
    reduce_access_rights,
)
from sqlalchemy.ext.asyncio import AsyncEngine

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


def test_reduce_access_rights():
    sample = ServiceAccessRightsAtDB.model_validate(
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


async def test_auto_upgrade_policy(
    sqlalchemy_async_engine: AsyncEngine,
    user_groups_ids: list[int],
    target_product: ProductName,
    other_product: ProductName,
    services_db_tables_injector: Callable,
    create_fake_service_data: Callable,
    mocker,
):
    everyone_gid, user_gid, team_gid = user_groups_ids

    # Avoids calls to director API
    mocker.patch(
        "simcore_service_catalog.services.access_rights._is_old_service",
        return_value=False,
    )
    # Avoids creating a users + user_to_group table
    data = GroupAtDB.model_config["json_schema_extra"]["example"]
    data["gid"] = everyone_gid
    mocker.patch(
        "simcore_service_catalog.services.access_rights.GroupsRepository.get_everyone_group",
        return_value=GroupAtDB.model_validate(data),
    )
    mocker.patch(
        "simcore_service_catalog.services.access_rights.GroupsRepository.get_user_gid_from_email",
        return_value=user_gid,
    )

    # SETUP ---
    MOST_UPDATED_EXAMPLE = -1
    new_service_metadata = ServiceMetaDataPublished.model_validate(
        ServiceMetaDataPublished.model_config["json_schema_extra"]["examples"][
            MOST_UPDATED_EXAMPLE
        ]
    )
    new_service_metadata.version = TypeAdapter(ServiceVersion).validate_python("1.0.11")

    # we have three versions of the service in the database for which the sorting matters: (1.0.11 should inherit from 1.0.10 not 1.0.9)
    await services_db_tables_injector(
        [
            create_fake_service_data(
                new_service_metadata.key,
                "1.0.1",
                team_access=None,
                everyone_access=None,
                product=target_product,
            ),
            create_fake_service_data(
                new_service_metadata.key,
                "1.0.9",
                team_access=None,
                everyone_access=None,
                product=target_product,
            ),
            # new release is a patch on released 1.0.X
            # which were released in two different product
            create_fake_service_data(
                new_service_metadata.key,
                "1.0.10",
                team_access="x",
                everyone_access=None,
                product=target_product,
            ),
            create_fake_service_data(
                new_service_metadata.key,
                "1.0.10",
                team_access="x",
                everyone_access=None,
                product=other_product,
            ),
        ]
    )
    # ------------

    app = FastAPI()
    app.state.engine = sqlalchemy_async_engine
    app.state.settings = mocker.Mock()
    app.state.default_product_name = target_product

    services_repo = ServicesRepository(app.state.engine)

    # DEFAULT policies
    owner_gid, service_access_rights = await evaluate_default_policy(
        app, new_service_metadata
    )
    assert owner_gid == user_gid
    assert len(service_access_rights) == 1
    assert {a.gid for a in service_access_rights} == {owner_gid}
    assert service_access_rights[0].model_dump() == {
        "key": new_service_metadata.key,
        "version": new_service_metadata.version,
        "gid": user_gid,
        "product_name": target_product,
        "execute_access": True,
        "write_access": True,
    }
    assert service_access_rights[0].product_name == target_product

    # AUTO-UPGRADE PATCH policy
    inherited_access_rights = await evaluate_auto_upgrade_policy(
        new_service_metadata, services_repo
    )

    assert len(inherited_access_rights) == 4
    assert {a.gid for a in inherited_access_rights} == {team_gid, owner_gid}
    assert {a.product_name for a in inherited_access_rights} == {
        target_product,
        other_product,
    }

    # ALL
    service_access_rights += inherited_access_rights
    service_access_rights = reduce_access_rights(service_access_rights)

    assert len(service_access_rights) == 4
    assert {a.gid for a in service_access_rights} == {team_gid, owner_gid}
    assert {a.product_name for a in service_access_rights} == {
        target_product,
        other_product,
    }
