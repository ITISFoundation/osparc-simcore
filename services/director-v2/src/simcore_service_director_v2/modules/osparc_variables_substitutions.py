""" Substitution of osparc variables and secrets

"""
import logging
from collections.abc import Callable, Mapping
from copy import deepcopy
from typing import Any

from fastapi import FastAPI
from models_library.osparc_variable_identifier import (
    UnresolvedOsparcVariableIdentifierError,
    raise_if_unresolved_osparc_variable_identifier_found,
    replace_osparc_variable_identifier,
)
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services import ServiceKey, ServiceVersion
from models_library.users import UserID
from models_library.utils.specs_substitution import SpecsSubstitutionsResolver
from pydantic import BaseModel, EmailStr
from servicelib.logging_utils import log_context

from ..utils.db import get_repository
from ..utils.osparc_variables import (
    ContextDict,
    OsparcVariablesTable,
    resolve_variables_from_context,
)
from .db.repositories.services_environments import ServicesEnvironmentsRepository

_logger = logging.getLogger(__name__)


async def substitute_vendor_secrets_in_model(
    app: FastAPI,
    model: BaseModel,
    *,
    safe: bool = True,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    product_name: ProductName,
) -> BaseModel:
    result: BaseModel = model
    try:
        with log_context(_logger, logging.DEBUG, "substitute_vendor_secrets_in_model"):
            # checks before to avoid unnecessary calls to pg
            # if it raises an error vars need replacement
            _logger.debug("model in which to replace model=%s", model)
            raise_if_unresolved_osparc_variable_identifier_found(model)
    except UnresolvedOsparcVariableIdentifierError:
        repo = get_repository(app, ServicesEnvironmentsRepository)
        vendor_secrets = await repo.get_vendor_secrets(
            service_key=service_key,
            service_version=service_version,
            product_name=product_name,
        )
        _logger.warning("replacing with the vendor_secrets=%s", vendor_secrets)
        result = replace_osparc_variable_identifier(model, vendor_secrets)

    if not safe:
        raise_if_unresolved_osparc_variable_identifier_found(result)

    return result


async def resolve_and_substitute_session_variables_in_model(
    app: FastAPI,
    model: BaseModel,
    *,
    safe: bool = True,
    user_id: UserID,
    product_name: str,
    project_id: ProjectID,
    node_id: NodeID,
) -> BaseModel:
    result: BaseModel = model
    try:
        with log_context(
            _logger, logging.DEBUG, "resolve_and_substitute_session_variables_in_model"
        ):
            # checks before to avoid unnecessary calls to pg
            # if it raises an error vars need replacement
            _logger.debug("model in which to replace model=%s", model)
            raise_if_unresolved_osparc_variable_identifier_found(model)
    except UnresolvedOsparcVariableIdentifierError:
        table: OsparcVariablesTable = app.state.session_variables_table
        identifiers = await resolve_variables_from_context(
            table.copy(),
            context=ContextDict(
                app=app,
                user_id=user_id,
                product_name=product_name,
                project_id=project_id,
                node_id=node_id,
            ),
        )
        _logger.debug("replacing with the identifiers=%s", identifiers)
        result = replace_osparc_variable_identifier(model, identifiers)

    if not safe:
        raise_if_unresolved_osparc_variable_identifier_found(result)

    return result


async def substitute_vendor_secrets_in_specs(
    app: FastAPI,
    specs: dict[str, Any],
    *,
    safe: bool = True,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    product_name: ProductName,
) -> dict[str, Any]:
    resolver = SpecsSubstitutionsResolver(specs, upgrade=False)
    repo = get_repository(app, ServicesEnvironmentsRepository)

    _logger.debug(
        "substitute_vendor_secrets_in_specs detected_identifiers=%s",
        resolver.get_identifiers(),
    )

    if any(repo.is_vendor_secret_identifier(idr) for idr in resolver.get_identifiers()):
        # checks before to avoid unnecessary calls to pg
        vendor_secrets = await repo.get_vendor_secrets(
            service_key=service_key,
            service_version=service_version,
            product_name=product_name,
        )
        _logger.debug(
            "substitute_vendor_secrets_in_specs stored_vendor_secrets=%s",
            vendor_secrets,
        )

        # resolve substitutions
        resolver.set_substitutions(mappings=vendor_secrets)
        new_specs: dict[str, Any] = resolver.run(safe=safe)
        return new_specs

    return deepcopy(specs)


async def resolve_and_substitute_session_variables_in_specs(
    app: FastAPI,
    specs: dict[str, Any],
    *,
    safe: bool = True,
    user_id: UserID,
    product_name: str,
    project_id: ProjectID,
    node_id: NodeID,
) -> dict[str, Any]:
    table: OsparcVariablesTable = app.state.session_variables_table
    resolver = SpecsSubstitutionsResolver(specs, upgrade=False)

    if requested := set(resolver.get_identifiers()):
        available = set(table.variables_names())

        if identifiers := available.intersection(requested):
            environs = await resolve_variables_from_context(
                table.copy(include=identifiers),
                context=ContextDict(
                    app=app,
                    user_id=user_id,
                    product_name=product_name,
                    project_id=project_id,
                    node_id=node_id,
                ),
            )

            resolver.set_substitutions(mappings=environs)
            new_specs: dict[str, Any] = resolver.run(safe=safe)
            return new_specs

    return deepcopy(specs)


async def resolve_and_substitute_lifespan_variables_in_specs(
    _app: FastAPI,
    _specs: dict[str, Any],
    *,
    _callbacks_registry: Mapping[str, Callable],
    safe: bool = True,
):
    raise NotImplementedError


async def _request_user_email(app: FastAPI, user_id: UserID) -> EmailStr:
    repo = get_repository(app, ServicesEnvironmentsRepository)
    return await repo.get_user_email(user_id=user_id)


async def _request_user_role(app: FastAPI, user_id: UserID):
    repo = get_repository(app, ServicesEnvironmentsRepository)
    return await repo.get_user_role(user_id=user_id)


def _setup_session_osparc_variables(app: FastAPI):
    app.state.session_variables_table = table = OsparcVariablesTable()

    # Registers some session osparc_variables
    # WARNING: context_name needs to match session_context!
    for name, context_name in [
        ("OSPARC_VARIABLE_PRODUCT_NAME", "product_name"),
        ("OSPARC_VARIABLE_STUDY_UUID", "project_id"),
        ("OSPARC_VARIABLE_NODE_ID", "node_id"),
    ]:
        table.register_from_context(name, context_name)

    table.register_from_handler("OSPARC_VARIABLE_USER_EMAIL")(_request_user_email)
    table.register_from_handler("OSPARC_VARIABLE_USER_ROLE")(_request_user_role)

    _logger.debug(
        "Registered session_variables_table=%s", sorted(table.variables_names())
    )


def setup(app: FastAPI):
    """
    **o2sparc variables and secrets** are identifiers-value maps that are substituted on the service specs (e.g. docker-compose).
        - **vendor secrets**: information set by a vendor on the platform. e.g. a vendor service license
        - **session variables**: some session information as "current user email" or the "current product name"
        - **lifespan variables**: produced before a service is started and cleaned up after it finishes (e.g. API tokens )
    """

    def on_startup() -> None:
        _setup_session_osparc_variables(app)

    app.add_event_handler("startup", on_startup)
