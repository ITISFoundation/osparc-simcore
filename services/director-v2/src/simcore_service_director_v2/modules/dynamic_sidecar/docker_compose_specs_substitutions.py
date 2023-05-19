import logging
from copy import deepcopy
from typing import Any, Callable, Mapping

from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.service_settings_labels import ComposeSpecLabelDict
from models_library.services import ServiceKey
from models_library.users import UserID
from models_library.utils.specs_substitution import SpecsSubstitutionsResolver
from pydantic import EmailStr

from ...utils.db import get_repository
from ...utils.substitutions_sessions import (
    ContextDict,
    SessionEnvironmentsTable,
    resolve_session_environments,
)
from ..db.repositories.services_environments import ServicesEnvironmentsRepository

_logger = logging.getLogger(__name__)


async def substitute_vendor_environments(
    app: FastAPI,
    compose_spec: ComposeSpecLabelDict,
    service_key: ServiceKey,
) -> ComposeSpecLabelDict:
    assert compose_spec  # nosec
    new_compose_spec: ComposeSpecLabelDict

    resolver = SpecsSubstitutionsResolver(compose_spec, upgrade=False)
    repo = get_repository(app, ServicesEnvironmentsRepository)

    if any(repo.is_vendor_secret_identifier(idr) for idr in resolver.get_identifiers()):
        # checks before to avoid unnecesary calls to pg
        vendor_secrets = await repo.get_vendor_secrets(service_key=service_key)

        # resolve substitutions
        resolver.set_substitutions(environs=vendor_secrets)
        new_compose_spec = resolver.run()
        return new_compose_spec

    return deepcopy(compose_spec)


async def substitute_session_environments(
    app: FastAPI,
    compose_spec: ComposeSpecLabelDict,
    user_id: UserID,
    product_name: str,
    project_id: ProjectID,
    node_id: NodeID,
) -> ComposeSpecLabelDict:
    assert compose_spec  # nosec
    new_compose_spec: ComposeSpecLabelDict

    table: SessionEnvironmentsTable = app.state.session_environments_table
    resolver = SpecsSubstitutionsResolver(compose_spec, upgrade=False)

    if requested := set(resolver.get_identifiers()):
        available = set(table.name_keys())

        if identifiers := available.intersection(requested):
            environs = await resolve_session_environments(
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
            new_compose_spec = resolver.run()

            return new_compose_spec
    return deepcopy(compose_spec)


async def substitute_request_environments(
    _app: FastAPI,
    _pod_compose_spec: dict[str, Any],
    _callbacks_registry: Mapping[str, Callable],
):
    raise NotImplementedError()


async def _request_user_email(app: FastAPI, user_id: UserID) -> EmailStr:
    repo = get_repository(app, ServicesEnvironmentsRepository)
    return await repo.get_user_email(user_id=user_id)


async def _request_user_role(app: FastAPI, user_id: UserID):
    repo = get_repository(app, ServicesEnvironmentsRepository)
    return await repo.get_user_role(user_id=user_id)


def setup_session_environments(app: FastAPI):
    app.state.session_environments_table = table = SessionEnvironmentsTable()

    # Registers some session oenvs
    # WARNING: context_name needs to match session_context!
    for name, context_name in [
        ("OSPARC_ENVIRONMENT_PRODUCT_NAME", "product_name"),
        ("OSPARC_ENVIRONMENT_STUDY_UUID", "project_id"),
        ("OSPARC_ENVIRONMENT_node_id", "node_id"),
    ]:
        table.register_from_context(name, context_name)

    table.register_from_handler("OSPARC_ENVIRONMENT_USER_EMAIL")(_request_user_email)
    table.register_from_handler("OSPARC_ENVIRONMENT_USER_ROLE")(_request_user_role)

    _logger.debug(
        "Registered session_environments_table=%s", sorted(list(table.name_keys()))
    )
