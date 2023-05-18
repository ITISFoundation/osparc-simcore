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
from simcore_service_director_v2.modules.dynamic_sidecar.docker_compose_specs_substitutions import (
    substitute_request_environments,
    substitute_session_environments,
    substitute_vendor_environments,
)
from simcore_service_director_v2.utils.substitutions_sessions import (
    ContextDict,
    factory_context_getter,
    factory_handler,
    resolve_session_environs,
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


async def test_resolve_session_environs(faker: Faker, session_context: ContextDict):
    assert substitute_session_environments
    assert substitute_vendor_environments
    assert substitute_request_environments

    # ----------------

    oenvs_table = {
        "OSPARC_ENVIRONMENT_PRODUCT_NAME": factory_context_getter("product_name"),
        "OSPARC_ENVIRONMENT_STUDY_UUID": factory_context_getter("project_id"),
        "OSPARC_ENVIRONMENT_NODE_UUID": factory_context_getter("node_id"),
    }

    # Here some callbacks

    async def request_user_email(app: FastAPI, user_id: UserID) -> SubstitutionValue:
        print(app, user_id)
        await asyncio.sleep(1)
        return faker.email()

    async def request_user_role(app: FastAPI, user_id: UserID) -> SubstitutionValue:
        print(app, user_id)
        await asyncio.sleep(1)
        return faker.random_element(elements=list(UserRole)).value

    oenvs_table |= {
        "OSPARC_ENVIRONMENT_USER_EMAIL": factory_handler(request_user_email),
        "OSPARC_ENVIRONMENT_USER_ROLE": factory_handler(request_user_role),
    }

    # Some context given ----------------------------------------------------------
    # TODO: test pre errors handling
    # TODO: test errors handling
    # TODO: test validation errors handling
    # TODO: test timeout error handling

    environs = await resolve_session_environs(oenvs_table, session_context)

    assert set(environs.keys()) == set(oenvs_table.keys())

    # All values extracted from the context MUST be SubstitutionValue
    assert {
        key: parse_obj_as(SubstitutionValue, value) for key, value in environs.items()
    }

    assert (
        environs["OSPARC_ENVIRONMENT_PRODUCT_NAME"] == session_context["product_name"]
    )
    assert environs["OSPARC_ENVIRONMENT_STUDY_UUID"] == session_context["project_id"]

    print(json.dumps(environs, indent=1))
