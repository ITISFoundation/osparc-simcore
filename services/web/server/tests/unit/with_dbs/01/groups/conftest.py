# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=too-many-statements
# pylint: disable=unused-argument
# pylint: disable=unused-variable


from collections.abc import Callable

import pytest
import sqlalchemy as sa
from aiohttp.test_utils import TestClient
from pytest_simcore.helpers.typing_env import EnvVarsDict
from servicelib.aiohttp.application import create_safe_application
from simcore_service_webserver.application_settings import setup_settings
from simcore_service_webserver.db.plugin import setup_db
from simcore_service_webserver.groups.plugin import setup_groups
from simcore_service_webserver.login.plugin import setup_login
from simcore_service_webserver.rest.plugin import setup_rest
from simcore_service_webserver.security.plugin import setup_security
from simcore_service_webserver.session.plugin import setup_session
from simcore_service_webserver.users.plugin import setup_users


@pytest.fixture
async def client(
    aiohttp_client: Callable,
    app_environment: EnvVarsDict,
    postgres_db: sa.engine.Engine,
) -> TestClient:
    app = create_safe_application()

    setup_settings(app)
    setup_db(app)
    setup_session(app)
    setup_security(app)
    setup_rest(app)
    setup_login(app)
    setup_users(app)
    setup_groups(app)

    return await aiohttp_client(app)
