# pylint: disable=no-value-for-parameter
# pylint: disable=not-an-iterable
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

"""
Regression tests for incomplete access-rights inheritance.

Background:
    The catalog background sync creates new service versions in the DB when they
    appear in the registry. Access rights are inherited from the latest compatible
    patch release. However, this inheritance can fail silently (e.g. due to race
    conditions between multiple catalog replicas, transient director API failures,
    or validation errors).

    Once a version is created with metadata but incomplete access rights, the sync
    never retries it — `_list_services_in_database` only checks `services_meta_data`,
    so the version appears "already synced".

    This was observed on sim4life.io with s4l-python-runner: from version 1.2.221
    onward, newly published versions only got owner access (gid=14) and lost team
    access (gid=31) for the s4l and s4lacad products. Users had to manually grant
    access after each publish.

Fix:
    `_ensure_access_rights_propagated` was added to `_run_sync_services` as a
    self-healing step. It scans consecutive patch versions within each major.minor
    group and copies forward any access rights that the predecessor has but the
    successor is missing, using `upsert_service_access_rights`.

    These tests verify both the isolated repair function and the full sync flow.

See also:
    - https://github.com/ITISFoundation/osparc-simcore/issues/7992
"""

from collections.abc import Callable
from typing import Any

import pytest
from fastapi import FastAPI
from models_library.groups import GroupID
from models_library.products import ProductName
from pytest_simcore.helpers.catalog_services import CreateFakeServiceDataCallable
from respx.router import MockRouter
from simcore_service_catalog.core.background_tasks import (
    _ensure_access_rights_propagated,
    _run_sync_services,
)
from simcore_service_catalog.repository.services import ServicesRepository
from sqlalchemy.ext.asyncio import AsyncEngine

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture
def services_repo(sqlalchemy_async_engine: AsyncEngine) -> ServicesRepository:
    return ServicesRepository(sqlalchemy_async_engine)


# ---------------------------------------------------------------------------
# Regression test: full _run_sync_services flow repairs incomplete rights
# ---------------------------------------------------------------------------


async def test_run_sync_services_repairs_incomplete_access_rights(
    background_task_lifespan_disabled: None,
    rabbitmq_and_rpc_setup_disabled: None,
    mocked_director_rest_api: MockRouter,
    expected_director_rest_api_list_services: list[dict[str, Any]],
    user: dict[str, Any],
    app: FastAPI,
    user_groups_ids: list[GroupID],
    target_product: ProductName,
    create_fake_service_data: CreateFakeServiceDataCallable,
    services_db_tables_injector: Callable,
    services_repo: ServicesRepository,
):
    """Regression: _run_sync_services must repair patch versions whose inheritance
    was incomplete during initial creation.

    Reproduces the s4l-python-runner scenario:
    - v1.0.0 was created with owner + team access
    - v1.0.1 was created but inheritance failed → only owner access
    - After sync, v1.0.1 should have team access propagated from v1.0.0
    """
    everyone_gid, user_gid, team_gid = user_groups_ids
    service_key = "simcore/services/comp/s4l-python-runner-regression"

    # --- Setup: simulate the broken state that occurs in production ---

    # v1.0.0: created correctly with owner + team access (full inheritance worked)
    await services_db_tables_injector(
        [
            create_fake_service_data(
                service_key,
                "1.0.0",
                team_access="x",
                everyone_access=None,
                product=target_product,
            ),
        ]
    )

    # v1.0.1: created with INCOMPLETE inheritance — only owner, no team
    # This is what happens when inherit_from_latest_compatible_release fails
    # silently (returns empty list) due to a transient error
    await services_db_tables_injector(
        [
            create_fake_service_data(
                service_key,
                "1.0.1",
                team_access=None,
                everyone_access=None,
                product=target_product,
            ),
        ]
    )

    # --- Verify the broken state ---
    rights_before = await services_repo.get_service_access_rights(service_key, "1.0.1")
    gids_before = {r.gid for r in rights_before}
    assert team_gid not in gids_before, "Precondition: team access is missing (the bug)"
    assert user_gid in gids_before, "Precondition: owner access exists"

    # --- Run the full sync cycle (the fix) ---
    await _run_sync_services(app)

    # --- Verify the repair ---
    rights_after = await services_repo.get_service_access_rights(service_key, "1.0.1")
    gids_after = {r.gid for r in rights_after}
    assert team_gid in gids_after, (
        "REGRESSION: team access was NOT propagated from v1.0.0 to v1.0.1. "
        "Without the self-healing step in _run_sync_services, versions with "
        "incomplete inheritance are never repaired."
    )

    # Verify the propagated right has the correct flags
    team_right = next(r for r in rights_after if r.gid == team_gid)
    assert team_right.execute_access is True
    assert team_right.write_access is False


async def test_run_sync_services_repairs_multi_product_rights(
    background_task_lifespan_disabled: None,
    rabbitmq_and_rpc_setup_disabled: None,
    mocked_director_rest_api: MockRouter,
    expected_director_rest_api_list_services: list[dict[str, Any]],
    user: dict[str, Any],
    app: FastAPI,
    user_groups_ids: list[GroupID],
    target_product: ProductName,
    other_product: ProductName,
    create_fake_service_data: CreateFakeServiceDataCallable,
    services_db_tables_injector: Callable,
    services_repo: ServicesRepository,
):
    """Regression: multi-product access rights are also repaired through full sync.

    On sim4life.io, services exist in multiple products (s4l, s4lacad, osparc).
    When inheritance fails, rights are lost for ALL products — the repair must
    restore them all.
    """
    everyone_gid, user_gid, team_gid = user_groups_ids
    service_key = "simcore/services/comp/multi-product-regression"

    # v1.0.0 has access for two products
    await services_db_tables_injector(
        [
            create_fake_service_data(
                service_key,
                "1.0.0",
                team_access="x",
                everyone_access=None,
                product=target_product,
            ),
            create_fake_service_data(
                service_key,
                "1.0.0",
                team_access="xw",
                everyone_access=None,
                product=other_product,
            ),
        ]
    )

    # v1.0.1 only has owner in one product (total inheritance failure)
    await services_db_tables_injector(
        [
            create_fake_service_data(
                service_key,
                "1.0.1",
                team_access=None,
                everyone_access=None,
                product=target_product,
            ),
        ]
    )

    await _run_sync_services(app)

    rights = await services_repo.get_service_access_rights(service_key, "1.0.1")
    rights_by_product_gid = {(r.product_name, r.gid): r for r in rights}

    assert (target_product, team_gid) in rights_by_product_gid, (
        "REGRESSION: team access for target product not restored"
    )
    assert (other_product, team_gid) in rights_by_product_gid, "REGRESSION: team access for other product not restored"
    assert rights_by_product_gid[(other_product, team_gid)].write_access is True


# ---------------------------------------------------------------------------
# Unit tests: _ensure_access_rights_propagated in isolation
# ---------------------------------------------------------------------------


async def test_propagation_repairs_missing_access_rights(
    user: dict[str, Any],
    user_groups_ids: list[GroupID],
    target_product: ProductName,
    create_fake_service_data: CreateFakeServiceDataCallable,
    services_db_tables_injector: Callable,
    services_repo: ServicesRepository,
    sqlalchemy_async_engine: AsyncEngine,
):
    """Basic case: newer patch version missing team access gets it from predecessor."""
    everyone_gid, user_gid, team_gid = user_groups_ids
    service_key = "simcore/services/comp/test-propagation"

    await services_db_tables_injector(
        [
            create_fake_service_data(
                service_key,
                "1.0.0",
                team_access="x",
                everyone_access=None,
                product=target_product,
            ),
        ]
    )
    await services_db_tables_injector(
        [
            create_fake_service_data(
                service_key,
                "1.0.1",
                team_access=None,
                everyone_access=None,
                product=target_product,
            ),
        ]
    )

    rights_before = await services_repo.get_service_access_rights(service_key, "1.0.1")
    assert team_gid not in {r.gid for r in rights_before}

    await _ensure_access_rights_propagated(sqlalchemy_async_engine)

    rights_after = await services_repo.get_service_access_rights(service_key, "1.0.1")
    gids_after = {r.gid for r in rights_after}
    assert team_gid in gids_after

    team_right = next(r for r in rights_after if r.gid == team_gid)
    assert team_right.execute_access is True
    assert team_right.write_access is False


async def test_propagation_chains_through_multiple_versions(
    user: dict[str, Any],
    user_groups_ids: list[GroupID],
    target_product: ProductName,
    create_fake_service_data: CreateFakeServiceDataCallable,
    services_db_tables_injector: Callable,
    services_repo: ServicesRepository,
    sqlalchemy_async_engine: AsyncEngine,
):
    """Propagation chains forward: v1.0.0 → v1.0.1 → v1.0.2."""
    everyone_gid, user_gid, team_gid = user_groups_ids
    service_key = "simcore/services/comp/test-chain"

    await services_db_tables_injector(
        [
            create_fake_service_data(
                service_key,
                "1.0.0",
                team_access="x",
                everyone_access=None,
                product=target_product,
            ),
        ]
    )
    await services_db_tables_injector(
        [
            create_fake_service_data(
                service_key,
                "1.0.1",
                team_access=None,
                everyone_access=None,
                product=target_product,
            ),
            create_fake_service_data(
                service_key,
                "1.0.2",
                team_access=None,
                everyone_access=None,
                product=target_product,
            ),
        ]
    )

    await _ensure_access_rights_propagated(sqlalchemy_async_engine)

    for version in ("1.0.1", "1.0.2"):
        rights = await services_repo.get_service_access_rights(service_key, version)
        assert team_gid in {r.gid for r in rights}, f"Team access missing on {version}"


async def test_propagation_does_not_cross_minor_versions(
    user: dict[str, Any],
    user_groups_ids: list[GroupID],
    target_product: ProductName,
    create_fake_service_data: CreateFakeServiceDataCallable,
    services_db_tables_injector: Callable,
    services_repo: ServicesRepository,
    sqlalchemy_async_engine: AsyncEngine,
):
    """Access rights from v1.0.x must NOT propagate to v1.1.x."""
    everyone_gid, user_gid, team_gid = user_groups_ids
    service_key = "simcore/services/comp/test-minor-boundary"

    await services_db_tables_injector(
        [
            create_fake_service_data(
                service_key,
                "1.0.0",
                team_access="x",
                everyone_access=None,
                product=target_product,
            ),
        ]
    )
    await services_db_tables_injector(
        [
            create_fake_service_data(
                service_key,
                "1.1.0",
                team_access=None,
                everyone_access=None,
                product=target_product,
            ),
        ]
    )

    await _ensure_access_rights_propagated(sqlalchemy_async_engine)

    rights = await services_repo.get_service_access_rights(service_key, "1.1.0")
    assert team_gid not in {r.gid for r in rights}, "Must NOT propagate across minor versions"


async def test_propagation_is_idempotent(
    user: dict[str, Any],
    user_groups_ids: list[GroupID],
    target_product: ProductName,
    create_fake_service_data: CreateFakeServiceDataCallable,
    services_db_tables_injector: Callable,
    services_repo: ServicesRepository,
    sqlalchemy_async_engine: AsyncEngine,
):
    """Running propagation multiple times produces the same result."""
    everyone_gid, user_gid, team_gid = user_groups_ids
    service_key = "simcore/services/comp/test-idempotent"

    await services_db_tables_injector(
        [
            create_fake_service_data(
                service_key,
                "1.0.0",
                team_access="x",
                everyone_access=None,
                product=target_product,
            ),
            create_fake_service_data(
                service_key,
                "1.0.1",
                team_access=None,
                everyone_access=None,
                product=target_product,
            ),
        ]
    )

    await _ensure_access_rights_propagated(sqlalchemy_async_engine)
    rights_first = await services_repo.get_service_access_rights(service_key, "1.0.1")

    await _ensure_access_rights_propagated(sqlalchemy_async_engine)
    rights_second = await services_repo.get_service_access_rights(service_key, "1.0.1")

    first_set = {(r.gid, r.product_name, r.execute_access, r.write_access) for r in rights_first}
    second_set = {(r.gid, r.product_name, r.execute_access, r.write_access) for r in rights_second}
    assert first_set == second_set


async def test_propagation_noop_when_all_rights_present(
    user: dict[str, Any],
    user_groups_ids: list[GroupID],
    target_product: ProductName,
    create_fake_service_data: CreateFakeServiceDataCallable,
    services_db_tables_injector: Callable,
    services_repo: ServicesRepository,
    sqlalchemy_async_engine: AsyncEngine,
):
    """No changes when all versions already have correct access rights."""
    everyone_gid, user_gid, team_gid = user_groups_ids
    service_key = "simcore/services/comp/test-noop"

    await services_db_tables_injector(
        [
            create_fake_service_data(
                service_key,
                "1.0.0",
                team_access="x",
                everyone_access=None,
                product=target_product,
            ),
            create_fake_service_data(
                service_key,
                "1.0.1",
                team_access="x",
                everyone_access=None,
                product=target_product,
            ),
        ]
    )

    rights_before = await services_repo.get_service_access_rights(service_key, "1.0.1")

    await _ensure_access_rights_propagated(sqlalchemy_async_engine)

    rights_after = await services_repo.get_service_access_rights(service_key, "1.0.1")

    before_set = {(r.gid, r.product_name, r.execute_access, r.write_access) for r in rights_before}
    after_set = {(r.gid, r.product_name, r.execute_access, r.write_access) for r in rights_after}
    assert before_set == after_set
