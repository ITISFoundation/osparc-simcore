# pylint: disable=no-value-for-parameter
# pylint: disable=not-an-iterable
# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from typing import AsyncIterator, Callable

import pytest
import sqlalchemy as sa
from pytest_simcore.helpers.rawdata_fakers import random_user
from respx.router import MockRouter
from simcore_postgres_database.models.groups import user_to_groups
from simcore_postgres_database.models.services import services_access_rights
from simcore_postgres_database.models.users import users
from sqlalchemy.ext.asyncio import AsyncEngine
from starlette.testclient import TestClient
from yarl import URL

pytest_simcore_core_services_selection = [
    "postgres",
]
pytest_simcore_ops_services_selection = [
    "adminer",
]


@pytest.fixture()
async def users_data(
    sqlalchemy_async_engine: AsyncEngine,
) -> AsyncIterator[list[str]]:
    """Inits user_to_groups db table"""
    random_users = [random_user() for _ in range(4)]

    # pylint: disable=no-value-for-parameter
    created_users = []
    async with sqlalchemy_async_engine.begin() as conn:
        for user in random_users:
            result = await conn.execute(users.insert().values(**user))
            user_id = result.returned_defaults[0]
            result = await conn.execute(
                sa.select([users.c.primary_gid]).where(users.c.id == user_id)
            )
            user_primary_gid = result.fetchone()[0]
            created_users.append((user_id, user_primary_gid))

    yield created_users

    async with sqlalchemy_async_engine.begin() as conn:
        for id_, _ in created_users:
            await conn.execute(users.delete().where(users.c.id == id_))


async def test_inaccessible_services_for_primary_group(
    mock_catalog_background_task: None,
    director_mockup: MockRouter,
    client: TestClient,
    user_id: int,
    products_names: list[str],
    service_catalog_faker: Callable,
    services_db_tables_injector: Callable,
    sqlalchemy_async_engine: AsyncEngine,
    users_data,
):
    target_product = products_names[0]  # osparc
    # create some fake services
    NUM_SERVICES = 3
    fake_services = [
        service_catalog_faker(
            "simcore/services/dynamic/jupyterlab",
            f"1.0.{s}",
            team_access=None,
            everyone_access=None,
            product=target_product,
        )
        for s in range(NUM_SERVICES)
    ]
    # injects fake data in db
    await services_db_tables_injector(fake_services)

    service_to_check = fake_services[0][0]  # --> service_meta_data table format

    # Currently only the owner has access to the service
    url = URL("/v0/services/inaccessible").with_query({"gid": 1})
    response = client.post(
        f"{url}",
        headers={"x-simcore-products-name": target_product},
        json={
            "services_to_check": [
                {
                    "key": service_to_check["key"],
                    "version": service_to_check["version"],
                },
            ]
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert user_id not in {item["user_id"] for item in data}
    assert len(data) == 4

    # We share the service with other user primary group
    insert_user_id, insert_user_primary_gid = users_data[0]
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            services_access_rights.insert()
            .values(
                key=service_to_check["key"],
                version=service_to_check["version"],
                gid=insert_user_primary_gid,
                execute_access=True,
                write_access=True,
            )
            .returning(services_access_rights)
        )
        # cleanup_after_test.append(result.returned_defaults[0])

    url = URL("/v0/services/inaccessible").with_query({"gid": 1})
    response = client.post(
        f"{url}",
        headers={"x-simcore-products-name": target_product},
        json={
            "services_to_check": [
                {
                    "key": service_to_check["key"],
                    "version": service_to_check["version"],
                },
            ]
        },
    )
    assert response.status_code == 200
    data = response.json()
    response_users = {item["user_id"] for item in data}
    assert user_id not in response_users
    assert insert_user_id not in response_users
    assert len(data) == 3


async def test_inaccessible_services_for_standard_group(
    mock_catalog_background_task: None,
    director_mockup: MockRouter,
    client: TestClient,
    user_groups_ids: list[int],
    user_id: int,
    products_names: list[str],
    service_catalog_faker: Callable,
    services_db_tables_injector: Callable,
    sqlalchemy_async_engine: AsyncEngine,
    users_data,
):
    _, _, _, team_yoda_gid = user_groups_ids
    target_product = products_names[1]  # s4l
    # create some fake services
    NUM_SERVICES = 3
    fake_services = [
        service_catalog_faker(
            f"simcore/services/dynamic/jupyterlab_{s}",
            "1.0.1",
            team_access=None,
            everyone_access=None,
            product=target_product,
        )
        for s in range(NUM_SERVICES)
    ]
    # injects fake data in db
    await services_db_tables_injector(fake_services)

    service_to_check = fake_services[0][0]  # --> service_meta_data table format

    # There are no users in this standard group therefore there the output should be empty
    url = URL("/v0/services/inaccessible").with_query({"gid": team_yoda_gid})
    response = client.post(
        f"{url}",
        headers={"x-simcore-products-name": target_product},
        json={
            "services_to_check": [
                {
                    "key": service_to_check["key"],
                    "version": service_to_check["version"],
                },
            ]
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 0

    # Add three users to the team yoda standard group
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            user_to_groups.insert().values(uid=user_id, gid=team_yoda_gid)
        )
        await conn.execute(
            user_to_groups.insert().values(uid=users_data[1][0], gid=team_yoda_gid)
        )
        await conn.execute(
            user_to_groups.insert().values(uid=users_data[2][0], gid=team_yoda_gid)
        )

    user_id, user_primary_gid = users_data[0]
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            services_access_rights.insert().values(
                key=service_to_check["key"],
                version=service_to_check["version"],
                gid=user_primary_gid,
                execute_access=True,
                write_access=True,
                product_name=products_names[1],
            )
        )
    url = URL("/v0/services/inaccessible").with_query({"gid": team_yoda_gid})
    response = client.post(
        f"{url}",
        headers={"x-simcore-products-name": target_product},
        json={
            "services_to_check": [
                {
                    "key": service_to_check["key"],
                    "version": service_to_check["version"],
                },
            ]
        },
    )
    assert response.status_code == 200
    data = response.json()
    # Only the user_id has access to the service through his primary group as he is the owner
    assert user_id not in {item["user_id"] for item in data}
    assert len(data) == 2

    # Now we give access to the service to another user
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            services_access_rights.insert().values(
                key=service_to_check["key"],
                version=service_to_check["version"],
                gid=users_data[1][1],
                execute_access=True,
                write_access=True,
                product_name=products_names[1],
            )
        )

    url = URL("/v0/services/inaccessible").with_query({"gid": team_yoda_gid})
    response = client.post(
        f"{url}",
        headers={"x-simcore-products-name": target_product},
        json={
            "services_to_check": [
                {
                    "key": service_to_check["key"],
                    "version": service_to_check["version"],
                },
            ]
        },
    )
    assert response.status_code == 200
    data = response.json()
    # Now only the last user has no access to the service
    response_users = {item["user_id"] for item in data}
    assert user_id not in response_users
    assert users_data[1][0] not in response_users
    assert len(data) == 1


async def test_inaccessible_services_for_more_services(
    mock_catalog_background_task: None,
    director_mockup: MockRouter,
    client: TestClient,
    user_id: int,
    products_names: list[str],
    service_catalog_faker: Callable,
    services_db_tables_injector: Callable,
    sqlalchemy_async_engine: AsyncEngine,
    users_data,
):
    target_product = products_names[1]  # s4l
    # create some fake services
    NUM_SERVICES = 3
    fake_services = [
        service_catalog_faker(
            "simcore/services/dynamic/jupyterlab",
            f"1.0.{s}",
            team_access=None,
            everyone_access=None,
            product=target_product,
        )
        for s in range(NUM_SERVICES)
    ]
    # injects fake data in db
    await services_db_tables_injector(fake_services)

    service_to_check_1 = fake_services[0][0]  # --> service_meta_data table format
    service_to_check_2 = fake_services[1][0]

    # Currently only the owner has access to the services
    url = URL("/v0/services/inaccessible").with_query({"gid": 1})
    response = client.post(
        f"{url}",
        headers={"x-simcore-products-name": target_product},
        json={
            "services_to_check": [
                {
                    "key": service_to_check_1["key"],
                    "version": service_to_check_1["version"],
                },
                {
                    "key": service_to_check_2["key"],
                    "version": service_to_check_2["version"],
                },
            ]
        },
    )
    assert response.status_code == 200
    data = response.json()
    response_users = {item["user_id"] for item in data}
    user_id not in response_users
    assert len(data) == 8

    # We share one service with other user primary group
    async with sqlalchemy_async_engine.begin() as conn:
        await conn.execute(
            services_access_rights.insert().values(
                key=service_to_check_1["key"],
                version=service_to_check_1["version"],
                gid=users_data[1][1],
                execute_access=True,
                write_access=True,
                product_name=products_names[1],
            )
        )
    url = URL("/v0/services/inaccessible").with_query({"gid": 1})
    response = client.post(
        f"{url}",
        headers={"x-simcore-products-name": target_product},
        json={
            "services_to_check": [
                {
                    "key": service_to_check_1["key"],
                    "version": service_to_check_1["version"],
                },
                {
                    "key": service_to_check_2["key"],
                    "version": service_to_check_2["version"],
                },
            ]
        },
    )
    assert response.status_code == 200
    data = response.json()
    response_users_and_services = {
        (item["user_id"], item["service_key"], item["service_version"]) for item in data
    }
    assert (
        users_data[1][0],
        service_to_check_1["key"],
        service_to_check_1["version"],
    ) not in response_users_and_services
    assert len(data) == 7
