# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable

from collections.abc import AsyncIterator, Iterator
from contextlib import ExitStack

import pytest
import sqlalchemy as sa
from common_library.json_serialization import json_dumps
from common_library.serialization import model_dump_with_secrets
from pytest_simcore.helpers.faker_factories import (
    random_service_access_rights,
    random_service_consume_filetype,
    random_service_meta_data,
)
from pytest_simcore.helpers.monkeypatch_envs import setenvs_from_dict
from pytest_simcore.helpers.postgres_tools import sync_insert_and_get_row_lifespan
from pytest_simcore.helpers.typing_env import EnvVarsDict
from settings_library.rabbit import RabbitSettings
from settings_library.redis import RedisSettings
from simcore_postgres_database.models.products import products
from simcore_postgres_database.models.services import (
    services_access_rights,
    services_meta_data,
)
from simcore_postgres_database.models.services_consume_filetypes import (
    services_consume_filetypes,
)
from simcore_service_webserver.studies_dispatcher.settings import (
    StudiesDispatcherSettings,
)
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
def app_environment(
    app_environment: EnvVarsDict,
    monkeypatch: pytest.MonkeyPatch,
    rabbit_service: RabbitSettings,
) -> EnvVarsDict:
    envs_plugins = setenvs_from_dict(
        monkeypatch,
        {
            "WEBSERVER_ACTIVITY": "null",
            "WEBSERVER_CATALOG": "null",
            "WEBSERVER_DIAGNOSTICS": "null",
            "WEBSERVER_EXPORTER": "null",
            "WEBSERVER_FUNCTIONS": "0",
            "WEBSERVER_GROUPS": "1",
            "WEBSERVER_NOTIFICATIONS": "0",
            "WEBSERVER_PRODUCTS": "1",
            "WEBSERVER_RABBITMQ": json_dumps(model_dump_with_secrets(rabbit_service, show_secrets=True)),
            "WEBSERVER_REMOTE_DEBUG": "0",
            "WEBSERVER_SOCKETIO": "0",
            "WEBSERVER_STORAGE": "null",
            "WEBSERVER_TAGS": "1",
            "WEBSERVER_TRACING": "null",
            "WEBSERVER_WALLETS": "0",
        },
    )

    monkeypatch.delenv("WEBSERVER_STUDIES_DISPATCHER", raising=False)
    app_environment.pop("WEBSERVER_STUDIES_DISPATCHER", None)

    envs_studies_dispatcher = setenvs_from_dict(
        monkeypatch,
        {
            "STUDIES_ACCESS_ANONYMOUS_ALLOWED": "1",
            "STUDIES_GUEST_ACCOUNT_LIFETIME": "2 1:10:00",  # 2 days 1h and 10 mins
        },
    )

    plugin_settings = StudiesDispatcherSettings.create_from_envs()
    print(plugin_settings.model_dump_json(indent=1))

    return {**app_environment, **envs_plugins, **envs_studies_dispatcher}


@pytest.fixture(scope="module")
def services_metadata_in_db(
    postgres_db: sa.engine.Engine,
) -> Iterator[list[dict]]:
    """Pre-populate services metadata table with test data maintaining original structure."""
    services_data = [
        random_service_meta_data(
            key="simcore/services/dynamic/raw-graphs",
            version="2.11.1",
            name="2D plot",
            description="2D plots powered by RAW Graphs",
            thumbnail=None,
        ),
        random_service_meta_data(
            key="simcore/services/dynamic/bio-formats-web",
            version="1.0.1",
            name="bio-formats",
            description="Bio-Formats image viewer",
            thumbnail="https://www.openmicroscopy.org/img/logos/bio-formats.svg",
        ),
        random_service_meta_data(
            key="simcore/services/dynamic/jupyter-octave-python-math",
            version="1.6.9",
            name="JupyterLab Math",
            description="JupyterLab Math with octave and python",
            thumbnail=None,
        ),
        random_service_meta_data(
            key="simcore/services/dynamic/s4l-ui-modeling",
            version="3.2.300",
            name="Hornet Flow",
            description="Hornet Flow UI for Sim4Life",
            thumbnail=None,
        ),
    ]

    with ExitStack() as stack:
        created_services = []
        for service_data in services_data:
            row = stack.enter_context(
                sync_insert_and_get_row_lifespan(
                    postgres_db,
                    table=services_meta_data,
                    values=service_data,
                    pk_cols=[services_meta_data.c.key, services_meta_data.c.version],
                )
            )
            created_services.append(row)

        yield created_services


@pytest.fixture(scope="module")
def services_consume_filetypes_in_db(
    postgres_db: sa.engine.Engine, services_metadata_in_db: list[dict]
) -> Iterator[list[dict]]:
    """Pre-populate services consume filetypes table with test data."""
    filetypes_data = [
        random_service_consume_filetype(
            service_key="simcore/services/dynamic/bio-formats-web",
            service_version="1.0.1",
            service_display_name="bio-formats",
            service_input_port="input_1",
            filetype="PNG",
            preference_order=0,
            is_guest_allowed=True,
        ),
        random_service_consume_filetype(
            service_key="simcore/services/dynamic/raw-graphs",
            service_version="2.11.1",
            service_display_name="RAWGraphs",
            service_input_port="input_1",
            filetype="CSV",
            preference_order=0,
            is_guest_allowed=True,
        ),
        random_service_consume_filetype(
            service_key="simcore/services/dynamic/bio-formats-web",
            service_version="1.0.1",
            service_display_name="bio-formats",
            service_input_port="input_1",
            filetype="JPEG",
            preference_order=0,
            is_guest_allowed=True,
        ),
        random_service_consume_filetype(
            service_key="simcore/services/dynamic/raw-graphs",
            service_version="2.11.1",
            service_display_name="RAWGraphs",
            service_input_port="input_1",
            filetype="TSV",
            preference_order=0,
            is_guest_allowed=True,
        ),
        random_service_consume_filetype(
            service_key="simcore/services/dynamic/raw-graphs",
            service_version="2.11.1",
            service_display_name="RAWGraphs",
            service_input_port="input_1",
            filetype="XLSX",
            preference_order=0,
            is_guest_allowed=True,
        ),
        random_service_consume_filetype(
            service_key="simcore/services/dynamic/raw-graphs",
            service_version="2.11.1",
            service_display_name="RAWGraphs",
            service_input_port="input_1",
            filetype="JSON",
            preference_order=0,
            is_guest_allowed=True,
        ),
        random_service_consume_filetype(
            service_key="simcore/services/dynamic/jupyter-octave-python-math",
            service_version="1.6.9",
            service_display_name="JupyterLab Math",
            service_input_port="input_1",
            filetype="PY",
            preference_order=0,
            is_guest_allowed=False,
        ),
        random_service_consume_filetype(
            service_key="simcore/services/dynamic/jupyter-octave-python-math",
            service_version="1.6.9",
            service_display_name="JupyterLab Math",
            service_input_port="input_1",
            filetype="IPYNB",
            preference_order=0,
            is_guest_allowed=False,
        ),
        random_service_consume_filetype(
            service_key="simcore/services/dynamic/s4l-ui-modeling",
            service_version="3.2.300",
            service_display_name="Hornet Flow",
            service_input_port="input_1",
            filetype="HORNET_REPO",
            preference_order=0,
            is_guest_allowed=False,
        ),
    ]

    with ExitStack() as stack:
        created_filetypes = []
        for filetype_data in filetypes_data:
            row = stack.enter_context(
                sync_insert_and_get_row_lifespan(
                    postgres_db,
                    table=services_consume_filetypes,
                    values=filetype_data,
                    pk_cols=[
                        services_consume_filetypes.c.service_key,
                        services_consume_filetypes.c.service_version,
                        services_consume_filetypes.c.filetype,
                    ],
                )
            )
            created_filetypes.append(row)

        yield created_filetypes


@pytest.fixture(scope="module")
def services_access_rights_in_db(
    postgres_db: sa.engine.Engine, services_metadata_in_db: list[dict]
) -> Iterator[list[dict]]:
    """Pre-populate services access rights table with test data."""
    access_rights_data = [
        random_service_access_rights(
            key="simcore/services/dynamic/raw-graphs",
            version="2.11.1",
            gid=1,  # everyone group
            execute_access=True,
            write_access=False,
            product_name="osparc",
        ),
        random_service_access_rights(
            key="simcore/services/dynamic/jupyter-octave-python-math",
            version="1.6.9",
            gid=1,  # everyone group
            execute_access=True,
            write_access=False,
            product_name="osparc",
        ),
        random_service_access_rights(
            key="simcore/services/dynamic/s4l-ui-modeling",
            version="3.2.300",
            gid=1,  # everyone group
            execute_access=True,
            write_access=False,
            product_name="osparc",
        ),
    ]

    with ExitStack() as stack:
        created_access_rights = []
        for access_data in access_rights_data:
            row = stack.enter_context(
                sync_insert_and_get_row_lifespan(
                    postgres_db,
                    table=services_access_rights,
                    values=access_data,
                    pk_cols=[
                        services_access_rights.c.key,
                        services_access_rights.c.version,
                        services_access_rights.c.gid,
                        services_access_rights.c.product_name,
                    ],
                )
            )
            created_access_rights.append(row)

        yield created_access_rights


@pytest.fixture
async def studies_dispatcher_enabled(
    asyncpg_engine: AsyncEngine,
    osparc_product_name: str,
    request: pytest.FixtureRequest,
) -> AsyncIterator[bool]:
    """
    Fixture to enable/disable the studies dispatcher for the current product.
    Default is True for existing tests. Tests can override by:

        @pytest.mark.parametrize("studies_dispatcher_enabled", [False])
        async def test_something(studies_dispatcher_enabled):
            ...
    """
    enabled_value = request.param if hasattr(request, "param") else True

    async with asyncpg_engine.begin() as conn:
        # Store old value
        old_value = await conn.scalar(
            sa.select(products.c.studies_dispatcher_enabled).where(products.c.name == osparc_product_name)
        )

        assert old_value is not None, (
            f"Expected product '{osparc_product_name}' to exist with a 'studies_dispatcher_enabled' value"
        )

        # Set requested value for test
        await conn.execute(
            sa.update(products)
            .values(studies_dispatcher_enabled=enabled_value)
            .where(products.c.name == osparc_product_name)
        )

    yield enabled_value

    # Restore old value
    async with asyncpg_engine.begin() as conn:
        await conn.execute(
            sa.update(products)
            .values(studies_dispatcher_enabled=old_value)
            .where(products.c.name == osparc_product_name)
        )


@pytest.fixture
async def pre_app_init(
    studies_dispatcher_enabled: bool,
    services_metadata_in_db: list[dict],
    services_consume_filetypes_in_db: list[dict],
    services_access_rights_in_db: list[dict],
    rabbit_service: RabbitSettings,
    redis_service: RedisSettings,
) -> None:
    """Ensures studies dispatcher fixtures are applied before app startup.

    Product settings are loaded into app cache during startup callbacks, so
    the feature flag and service data must be set before the app starts.
    """
