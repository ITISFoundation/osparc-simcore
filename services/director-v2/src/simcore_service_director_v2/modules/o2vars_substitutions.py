import logging
from collections.abc import Callable, Mapping
from copy import deepcopy
from typing import Any

from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services import ServiceKey, ServiceVersion
from models_library.users import UserID
from models_library.utils.specs_substitution import SpecsSubstitutionsResolver
from pydantic import EmailStr

from ..utils.db import get_repository
from ..utils.session_o2vars import (
    ContextDict,
    SessionVariablesTable,
    resolve_session_variables,
)
from .db.repositories.services_environments import ServicesEnvironmentsRepository

_logger = logging.getLogger(__name__)


async def substitute_vendor_secrets_o2vars(
    app: FastAPI,
    specs: dict[str, Any],
    service_key: ServiceKey,
    service_version: ServiceVersion,
) -> dict[str, Any]:
    assert specs  # nosec
    resolver = SpecsSubstitutionsResolver(specs, upgrade=False)
    repo = get_repository(app, ServicesEnvironmentsRepository)

    if any(repo.is_vendor_secret_identifier(idr) for idr in resolver.get_identifiers()):
        # checks before to avoid unnecesary calls to pg
        vendor_secrets = await repo.get_vendor_secrets(
            service_key=service_key, service_version=service_version
        )

        # resolve substitutions
        resolver.set_substitutions(environs=vendor_secrets)
        return resolver.run()

    return deepcopy(specs)


async def substitute_session_o2vars(
    app: FastAPI,
    specs: dict[str, Any],
    user_id: UserID,
    product_name: str,
    project_id: ProjectID,
    node_id: NodeID,
) -> dict[str, Any]:

    assert specs  # nosec

    table: SessionVariablesTable = app.state.session_environments_table
    resolver = SpecsSubstitutionsResolver(specs, upgrade=False)

    if requested := set(resolver.get_identifiers()):
        available = set(table.name_keys())

        if identifiers := available.intersection(requested):
            environs = await resolve_session_variables(
                table.copy(include=identifiers),
                session_context=ContextDict(
                    app=app,
                    user_id=user_id,
                    product_name=product_name,
                    project_id=project_id,
                    node_id=node_id,
                ),
            )

            resolver.set_substitutions(environs=environs)
            return resolver.run()

    return deepcopy(specs)


async def substitute_lifespan_o2vars(
    _app: FastAPI,
    _specs: dict[str, Any],
    _callbacks_registry: Mapping[str, Callable],
):
    raise NotImplementedError


async def _request_user_email(app: FastAPI, user_id: UserID) -> EmailStr:
    repo = get_repository(app, ServicesEnvironmentsRepository)
    return await repo.get_user_email(user_id=user_id)


async def _request_user_role(app: FastAPI, user_id: UserID):
    repo = get_repository(app, ServicesEnvironmentsRepository)
    return await repo.get_user_role(user_id=user_id)


def _setup_session_o2vars(app: FastAPI):
    app.state.session_environments_table = table = SessionVariablesTable()

    # Registers some session oenvs
    # WARNING: context_name needs to match session_context!
    for name, context_name in [
        ("OSPARC_ENVIRONMENT_PRODUCT_NAME", "product_name"),
        ("OSPARC_ENVIRONMENT_STUDY_UUID", "project_id"),
        ("OSPARC_ENVIRONMENT_NODE_ID", "node_id"),
    ]:
        table.register_from_context(name, context_name)

    table.register_from_handler("OSPARC_ENVIRONMENT_USER_EMAIL")(_request_user_email)
    table.register_from_handler("OSPARC_ENVIRONMENT_USER_ROLE")(_request_user_role)

    _logger.debug("Registered session_environments_table=%s", sorted(table.name_keys()))


def setup(app: FastAPI):
    """
    **o2sparc-variables** (*o2vars* in short) are identifiers-value maps that are substituted on the service specs (e.g. docker-compose).
        - **vendor secrets**: information set by a vendor on the platform. e.g. a vendor service license
        - **session o2vars**: some session information as "current user email" or the "current product name"
        - **lifespan o2vars**: produced  before a service is started and cleaned up after it finishes (e.g. API tokens )
    """

    def on_startup() -> None:
        _setup_session_o2vars(app)

    app.add_event_handler("startup", on_startup)
