# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import Callable, List

import pytest
from aiopg.sa.engine import Engine
from fastapi import FastAPI
from models_library.services import ServiceAccessRightsAtDB, ServiceDockerData
from pytest_simcore.helpers.utils_mock import future_with_result
from simcore_service_catalog.db.repositories.services import ServicesRepository
from simcore_service_catalog.models.domain.group import GroupAtDB
from simcore_service_catalog.services.access_rights import (
    evaluate_auto_upgrade_policy,
    evaluate_default_policy,
    merge_access_rights,
)

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


def test_merge_access_rights():
    sample = ServiceAccessRightsAtDB.parse_obj(
        {
            "key": "simcore/services/dynamic/sim4life",
            "version": "1.0.9",
            "gid": 8,
            "execute_access": True,
            "write_access": True,
            "product_name": "osparc",
        }
    )

    # overrides and with other products
    merged = merge_access_rights(
        [
            sample.copy(deep=True),
            sample.copy(deep=True),
            sample.copy(update={"execute_access": False}, deep=True),
            sample.copy(update={"product_name": "s4l"}),
        ]
    )

    assert len(merged) == 2
    assert merged[0].get_flags() == {"execute_access": True, "write_access": True}

    merged = merge_access_rights(
        [
            sample.copy(deep=True),
            sample.copy(
                update={"gid": 1, "execute_access": True, "write_access": False},
                deep=True,
            ),
        ]
    )


async def test_auto_upgrade_policy(
    aiopg_engine: Engine,
    user_groups_ids: List[int],
    products_names: List[str],
    services_db_tables_injector: Callable,
    service_catalog_faker: Callable,
    mocker,
):
    everyone_gid, user_gid, team_gid = user_groups_ids
    target_product = products_names[0]

    # Avoids calls to director API
    mocker.patch(
        "simcore_service_catalog.services.access_rights._is_old_service",
        return_value=future_with_result(False),
    )
    # Avoids creating a users + user_to_group table
    data = GroupAtDB.Config.schema_extra["example"]
    data["gid"] = everyone_gid
    mocker.patch(
        "simcore_service_catalog.services.access_rights.GroupsRepository.get_everyone_group",
        return_value=future_with_result(GroupAtDB.parse_obj(data)),
    )
    mocker.patch(
        "simcore_service_catalog.services.access_rights.GroupsRepository.get_user_gid_from_email",
        return_value=future_with_result(user_gid),
    )

    # SETUP ---
    new_service_metadata = ServiceDockerData.parse_obj(
        ServiceDockerData.Config.schema_extra["example"]
    )
    new_service_metadata.version = "1.0.1"

    # we two versions of the service in the database
    await services_db_tables_injector(
        [
            service_catalog_faker(
                new_service_metadata.key,
                "0.5.0",
                team_access=None,
                everyone_access=None,
                product=target_product,
            ),
            service_catalog_faker(
                new_service_metadata.key,
                "1.0.0",
                team_access="x",
                everyone_access=None,
                product=target_product,
            ),
            service_catalog_faker(
                new_service_metadata.key,
                "1.0.0",
                team_access="x",
                everyone_access=None,
                product=products_names[-1],
            ),
        ]
    )
    # ------------

    app = FastAPI()
    app.state.engine = aiopg_engine
    app.state.settings = mocker.Mock()
    app.state.settings.access_rights_default_product_name = target_product

    services_repo = ServicesRepository(app.state.engine)

    # DEFAULT policies
    owner_gid, service_access_rights = await evaluate_default_policy(
        app, new_service_metadata
    )
    assert owner_gid == user_gid
    assert len(service_access_rights) == 1
    assert {a.gid for a in service_access_rights} == {owner_gid}
    assert service_access_rights[0].dict() == {
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
        products_names[-1],
    }

    # ALL
    service_access_rights += inherited_access_rights
    service_access_rights = merge_access_rights(service_access_rights)

    assert len(service_access_rights) == 3
    assert {a.gid for a in service_access_rights} == {team_gid, owner_gid}
    assert {a.product_name for a in service_access_rights} == {
        target_product,
        products_names[-1],
    }


@pytest.mark.skip(reason="dev")
def test_it2(services_catalog):

    # service S has a new patch released: 1.2.5 (i.e. backwards compatible bug fix, according to semver policies )
    current_version = "1.10.5"
    new_version = "1.10.6"

    # the owner of service, checked the auto-upgrade patch policy in the publication contract (i.e.metadata.yml)

    # service S:1.2.5 gets automatically the same access rights as S:1.2.4.
    # access_rights = get_access_rights(service_key, service_version)

    # set_access_rights(service_key, service_version, access_rights)

    # NO
    # all projects with nodes assigned to S:1.2.X get promoted to the latest patch S:1.2.5

    # services can be published on different products (including file-picker and group nodes)
