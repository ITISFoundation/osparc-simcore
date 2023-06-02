# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
import json

import pytest
from faker import Faker
from fastapi import FastAPI
from models_library.services import ServiceKey, ServiceVersion
from models_library.users import UserID
from models_library.utils.specs_substitution import SubstitutionValue
from pydantic import parse_obj_as
from pytest_simcore.helpers.faker_compose_specs import generate_fake_docker_compose
from simcore_postgres_database.models.users import UserRole
from simcore_service_director_v2.modules.oenvs_substitutions import (
    substitute_lifespan_oenvs,
    substitute_session_oenvs,
    substitute_vendor_secrets_oenvs,
)
from simcore_service_director_v2.utils.session_oenvs import (
    ContextDict,
    SessionEnvironmentsTable,
    factory_context_getter,
    factory_handler,
    resolve_session_environments,
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


@pytest.mark.acceptance_test
async def test_resolve_session_environs(faker: Faker, session_context: ContextDict):
    assert substitute_session_oenvs
    assert substitute_vendor_secrets_oenvs
    assert substitute_lifespan_oenvs

    async def _request_user_role(app: FastAPI, user_id: UserID) -> SubstitutionValue:
        print(app, user_id)
        await asyncio.sleep(1)
        return faker.random_element(elements=list(UserRole)).value

    # REGISTRATION -----
    oenvs_table = SessionEnvironmentsTable()

    # bulk registration
    oenvs_table.register(
        {
            "OSPARC_ENVIRONMENT_PRODUCT_NAME": factory_context_getter("product_name"),
            "OSPARC_ENVIRONMENT_STUDY_UUID": factory_context_getter("project_id"),
            "OSPARC_ENVIRONMENT_USER_ROLE": factory_handler(_request_user_role),
        }
    )

    # single entry
    oenvs_table.register_from_context("OSPARC_ENVIRONMENT_NODE_UUID", "node_id")

    # using decorator
    @oenvs_table.register_from_handler("OSPARC_ENVIRONMENT_USER_EMAIL")
    async def request_user_email(app: FastAPI, user_id: UserID) -> SubstitutionValue:
        print(app, user_id)
        await asyncio.sleep(1)
        return faker.email()

    # Some context given ----------------------------------------------------------
    # TODO: test pre errors handling
    # TODO: test errors handling
    # TODO: test validation errors handling
    # TODO: test timeout error handling

    environs = await resolve_session_environments(oenvs_table.copy(), session_context)

    assert set(environs.keys()) == set(oenvs_table.name_keys())

    # All values extracted from the context MUST be SubstitutionValue
    assert {
        key: parse_obj_as(SubstitutionValue, value) for key, value in environs.items()
    }

    for oenv_name, context_name in [
        ("OSPARC_ENVIRONMENT_PRODUCT_NAME", "product_name"),
        ("OSPARC_ENVIRONMENT_STUDY_UUID", "project_id"),
        ("OSPARC_ENVIRONMENT_NODE_UUID", "node_id"),
    ]:
        assert environs[oenv_name] == session_context[context_name]

    print(json.dumps(environs, indent=1))
