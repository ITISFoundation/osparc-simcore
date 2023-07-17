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
from simcore_service_director_v2.modules.osparc_variables_substitutions import (
    resolve_and_substitute_lifespan_variables_in_specs,
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
    assert resolve_and_substitute_session_variables_in_specs
    assert substitute_vendor_secrets_in_specs
    assert resolve_and_substitute_lifespan_variables_in_specs

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
