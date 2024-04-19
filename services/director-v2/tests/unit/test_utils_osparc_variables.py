# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
import json
from collections.abc import AsyncIterable
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, Mock

import pytest
from asgi_lifespan import LifespanManager
from faker import Faker
from fastapi import FastAPI
from models_library.api_schemas_webserver.auth import ApiKeyGet
from models_library.services import RunID, ServiceKey, ServiceVersion
from models_library.users import UserID
from models_library.utils.specs_substitution import SubstitutionValue
from models_library.utils.string_substitution import OSPARC_IDENTIFIER_PREFIX
from pydantic import parse_obj_as
from pytest_mock import MockerFixture
from pytest_simcore.helpers.faker_compose_specs import generate_fake_docker_compose
from simcore_postgres_database.models.services_environments import VENDOR_SECRET_PREFIX
from simcore_postgres_database.models.users import UserRole
from simcore_service_director_v2.api.dependencies.database import RepoType
from simcore_service_director_v2.modules import osparc_variables_substitutions
from simcore_service_director_v2.modules.osparc_variables_substitutions import (
    resolve_and_substitute_service_lifetime_variables_in_specs,
    resolve_and_substitute_session_variables_in_specs,
    substitute_vendor_secrets_in_specs,
)
from simcore_service_director_v2.utils.osparc_variables import (
    ContextDict,
    OsparcVariablesTable,
    factory_context_getter,
    factory_handler,
    resolve_variables_from_context,
)


@pytest.fixture
def session_context(faker: Faker) -> ContextDict:
    return ContextDict(
        app=FastAPI(),
        service_key=parse_obj_as(ServiceKey, "simcore/services/dynamic/foo"),
        service_version=parse_obj_as(ServiceVersion, "1.2.3"),
        compose_spec=generate_fake_docker_compose(faker),
        product_name=faker.word(),
        project_id=faker.uuid4(),
        user_id=faker.pyint(),
        node_id=faker.uuid4(),
    )


@pytest.mark.acceptance_test()
async def test_resolve_session_environs(faker: Faker, session_context: ContextDict):
    async def _request_user_role(app: FastAPI, user_id: UserID) -> SubstitutionValue:
        print(app, user_id)
        await asyncio.sleep(1)
        return faker.random_element(elements=list(UserRole)).value

    # REGISTRATION -----
    osparc_variables_table = OsparcVariablesTable()

    # bulk registration
    osparc_variables_table.register(
        {
            "OSPARC_VARIABLE_PRODUCT_NAME": factory_context_getter("product_name"),
            "OSPARC_VARIABLE_STUDY_UUID": factory_context_getter("project_id"),
            "OSPARC_VARIABLE_USER_ROLE": factory_handler(_request_user_role),
        }
    )

    # single entry
    osparc_variables_table.register_from_context("OSPARC_VARIABLE_NODE_UUID", "node_id")

    # using decorator
    @osparc_variables_table.register_from_handler("OSPARC_VARIABLE_USER_EMAIL")
    async def request_user_email(app: FastAPI, user_id: UserID) -> SubstitutionValue:
        print(app, user_id)
        await asyncio.sleep(1)
        return faker.email()

    # Some context given ----------------------------------------------------------
    # TODO: test pre errors handling
    # TODO: test errors handling
    # TODO: test validation errors handling
    # TODO: test timeout error handling

    environs = await resolve_variables_from_context(
        osparc_variables_table.copy(), session_context
    )

    assert set(environs.keys()) == set(osparc_variables_table.variables_names())

    # All values extracted from the context MUST be SubstitutionValue
    assert {
        key: parse_obj_as(SubstitutionValue, value) for key, value in environs.items()
    }

    for osparc_variable_name, context_name in [
        ("OSPARC_VARIABLE_PRODUCT_NAME", "product_name"),
        ("OSPARC_VARIABLE_STUDY_UUID", "project_id"),
        ("OSPARC_VARIABLE_NODE_UUID", "node_id"),
    ]:
        assert environs[osparc_variable_name] == session_context[context_name]

    print(json.dumps(environs, indent=1))


@pytest.fixture
def mock_repo_db_engine(mocker: MockerFixture) -> None:
    @asynccontextmanager
    async def _acquire():
        yield

    mocked_engine = AsyncMock()
    mocked_engine.acquire = _acquire

    def _get_repository(app: FastAPI, repo_type: type[RepoType]) -> RepoType:
        return repo_type(db_engine=mocked_engine)

    mocker.patch(
        "simcore_service_director_v2.modules.osparc_variables_substitutions.get_repository",
        side_effect=_get_repository,
    )


@pytest.fixture
def mock_user_repo(mocker: MockerFixture, mock_repo_db_engine: None) -> None:
    base = "simcore_service_director_v2.modules.db.repositories.users"
    mocker.patch(f"{base}.UsersRepo.get_role", return_value=UserRole("USER"))
    mocker.patch(f"{base}.UsersRepo.get_email", return_value="e@ma.il")


@pytest.fixture
async def fake_app(faker: Faker) -> AsyncIterable[FastAPI]:
    app = FastAPI()
    app.state.engine = AsyncMock()

    mock_settings = Mock()
    mock_settings.DIRECTOR_V2_PUBLIC_API_BASE_URL = faker.url()
    app.state.settings = mock_settings

    osparc_variables_substitutions.setup(app)

    async with LifespanManager(app):
        yield app


async def test_resolve_and_substitute_session_variables_in_specs(
    mock_user_repo: None, fake_app: FastAPI, faker: Faker
):
    specs = {
        "product_name": "${OSPARC_VARIABLE_PRODUCT_NAME}",
        "study_uuid": "${OSPARC_VARIABLE_STUDY_UUID}",
        "node_id": "${OSPARC_VARIABLE_NODE_ID}",
        "user_id": "${OSPARC_VARIABLE_USER_ID}",
        "email": "${OSPARC_VARIABLE_USER_EMAIL}",
        "user_role": "${OSPARC_VARIABLE_USER_ROLE}",
    }
    print("SPECS\n", specs)

    replaced_specs = await resolve_and_substitute_session_variables_in_specs(
        fake_app,
        specs=specs,
        user_id=1,
        product_name="a_product",
        project_id=faker.uuid4(cast_to=None),
        node_id=faker.uuid4(cast_to=None),
    )
    print("REPLACED SPECS\n", replaced_specs)

    assert OSPARC_IDENTIFIER_PREFIX not in f"{replaced_specs}"


@pytest.fixture
def mock_api_key_manager(mocker: MockerFixture) -> None:
    mocker.patch(
        "simcore_service_director_v2.modules.osparc_variables_substitutions.get_or_create_api_key",
        return_value=ApiKeyGet.parse_obj(ApiKeyGet.Config.schema_extra["examples"][0]),
    )


async def test_resolve_and_substitute_service_lifetime_variables_in_specs(
    mock_api_key_manager: None, fake_app: FastAPI, faker: Faker
):
    specs = {
        "api_key": "${OSPARC_VARIABLE_API_KEY}",
        "api_secret": "${OSPARC_VARIABLE_API_SECRET}",
    }
    print("SPECS\n", specs)

    replaced_specs = await resolve_and_substitute_service_lifetime_variables_in_specs(
        fake_app,
        specs=specs,
        user_id=1,
        product_name="a_product",
        node_id=faker.uuid4(cast_to=None),
        run_id=RunID.create(),
    )
    print("REPLACED SPECS\n", replaced_specs)

    assert OSPARC_IDENTIFIER_PREFIX not in f"{replaced_specs}"


@pytest.fixture
def mock_get_vendor_secrets(mocker: MockerFixture, mock_repo_db_engine: None) -> None:
    base = "simcore_service_director_v2.modules.db.repositories.services_environments"
    mocker.patch(
        f"{base}.get_vendor_secrets",
        return_value={
            "OSPARC_VARIABLE_VENDOR_SECRET_ONE": 1,
            "OSPARC_VARIABLE_VENDOR_SECRET_TWO": "two",
        },
    )


async def test_substitute_vendor_secrets_in_specs(
    mock_get_vendor_secrets: None, fake_app: FastAPI, faker: Faker
):
    specs = {
        "api_key": "${OSPARC_VARIABLE_VENDOR_SECRET_ONE}",
        "api_secret": "${OSPARC_VARIABLE_VENDOR_SECRET_TWO}",
    }
    print("SPECS\n", specs)

    replaced_specs = await substitute_vendor_secrets_in_specs(
        fake_app,
        specs=specs,
        product_name="a_product",
        service_key=ServiceKey("simcore/services/dynamic/fake"),
        service_version=ServiceVersion("0.0.1"),
    )
    print("REPLACED SPECS\n", replaced_specs)

    assert VENDOR_SECRET_PREFIX not in f"{replaced_specs}"
