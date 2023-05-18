# pylint: disable=protected-access
# pylint: disable=redefined-outer-name
# pylint: disable=too-many-arguments
# pylint: disable=unused-argument
# pylint: disable=unused-variable


import asyncio
import inspect
import json
from typing import Any, Callable, NamedTuple, TypeAlias

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

ContextDict: TypeAlias = dict[str, Any]
ContextGetter: TypeAlias = Callable[[ContextDict], Any]


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


async def test_it(faker: Faker, session_context: ContextDict):
    assert substitute_session_environments
    assert substitute_vendor_environments
    assert substitute_request_environments

    # Registered
    class CaptureError(ValueError):
        ...

    def factory_context_getter(parameter_name: str) -> ContextGetter:
        """Factory that creates a function that gets a context as argument and gets a named parameter

        i.e. create_context_getter("foo")(context) == context["foo"]
        """

        def _get_or_raise(context: ContextDict) -> Any:
            try:
                return context[parameter_name]
            except KeyError as err:
                raise CaptureError(
                    "Parameter {keyname} missing from substitution context"
                ) from err

        # For context["foo"] -> return operator.methodcaller("__getitem__", keyname)
        # For context.foo -> return operator.attrgetter("project_id")
        return _get_or_raise

    class RequestTuple(NamedTuple):
        handler: Callable
        kwargs: dict[str, Any]

    def factory_handler(coro: Callable) -> Callable[[ContextDict], RequestTuple]:
        assert inspect.iscoroutinefunction(coro)  # nosec

        def _create(context: ContextDict):
            # NOTE: we could delay this as well ...
            kwargs_from_context = {
                param.name: factory_context_getter(param.name)(context)
                for param in inspect.signature(request_user_role).parameters.values()
            }
            return RequestTuple(handler=coro, kwargs=kwargs_from_context)

        return _create

    # ----------------

    oenvs_table = {
        "OSPARC_ENVIRONMENT_PRODUCT_NAME": factory_context_getter("product_name"),
        "OSPARC_ENVIRONMENT_STUDY_UUID": factory_context_getter("project_id"),
        "OSPARC_ENVIRONMENT_NODE_UUID": factory_context_getter("node_id"),
    }

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

    # prepares environs from context:
    pre_environs: dict[str, SubstitutionValue | RequestTuple] = {
        key: fun(session_context) for key, fun in oenvs_table.items()
    }

    # execute
    environs: dict[str, SubstitutionValue] = {}

    coros = {}
    for key, value in pre_environs.items():
        if isinstance(value, RequestTuple):
            handler, kwargs = value
            coro = handler(**kwargs)
            # wraps to control timeout
            coros[key] = asyncio.wait_for(coro, timeout=3)
        else:
            environs[key] = value

    values = await asyncio.gather(*coros.values())
    for key, value in zip(coros.keys(), values):
        environs[key] = value

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
