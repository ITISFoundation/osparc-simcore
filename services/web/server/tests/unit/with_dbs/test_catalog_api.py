# pylint:disable=unused-variable
# pylint:disable=unused-argument
# pylint:disable=redefined-outer-name

from copy import deepcopy

import pytest
from aiohttp import web

from simcore_service_webserver.application import (create_safe_application,
                                                   setup_catalog, setup_db,
                                                   setup_login, setup_rest,
                                                   setup_security,
                                                   setup_session)
from simcore_service_webserver.db_models import UserRole
from utils_login import LoggedUser


@pytest.fixture()
async def logged_user(client, user_role: UserRole):
    """ adds a user in db and logs in with client

    NOTE: `user_role` fixture is defined as a parametrization below!!!
    """
    async with LoggedUser(
        client,
        {"role": user_role.name},
        check_if_succeeds = user_role!=UserRole.ANONYMOUS
    ) as user:
        print("-----> logged in user", user_role)
        yield user
        print("<----- logged out user", user_role)


@pytest.fixture()
async def client(loop, app_cfg, aiohttp_client, postgres_db):
    # fixture: minimal client with catalog-subsystem enabled and
    #   only pertinent modules
    #
    # - Mocks calls to actual API

    cfg = deepcopy(app_cfg)

    cfg["db"]["init_tables"] = True # inits tables of postgres_service upon startup
    cfg['catalog']['enabled'] = True

    app = create_safe_application(app_cfg)

    # patch all
    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_login(app)            # needed for login_utils fixtures
    assert setup_catalog(app)

    yield loop.run_until_complete( aiohttp_client( app,
         server_kwargs={
             'port':app_cfg["main"]["port"]
        })
    )




# TODO: with different user roles, i.e. access rights
@pytest.mark.parametrize("user_role,expected", [
    #(UserRole.ANONYMOUS, web.HTTPUnauthorized),
    #(UserRole.GUEST, web.HTTPOk),
    (UserRole.USER, web.HTTPOk),
    #(UserRole.TESTER, web.HTTPOk),
])
async def test_dag_resource(client, logged_user, expected, api_version_prefix, mocker):
    v = api_version_prefix

    # from .login.decorators import login_required
    v = api_version_prefix

    # create resource
    data = {} # TODO: some fake data
    res = await client.post(f"/{v}/catalog/dags", json=data)
    assert res.status == 200

    # list resources
    res = await client.get(f"/{v}/catalog/dags")
    assert res.status == 200

    # get resource
    dag_id = 0
    res = await client.get(f"/{v}/catalog/dags/{dag_id}")
    assert res.status == 200

    # replace resource
    new_data = {} # TODO: some fake data
    res = await client.put(f"/{v}/dags/{dag_id}", json=new_data)
    assert res.status == 200

    # update resource
    patch_data = {} # TODO: some patch fake
    res = await client.patch(f"/{v}/dags/{dag_id}", json=patch_data)
    assert res.status == 200

    # delete
    res = await client.delete(f"/{v}/dags/{dag_id}")
    assert res.status == 200
