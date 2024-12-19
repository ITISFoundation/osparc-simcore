""" Substitution of osparc variables and secrets

"""

import functools
import logging
from copy import deepcopy
from typing import Any, Final, TypeVar

from fastapi import FastAPI
from models_library.osparc_variable_identifier import (
    UnresolvedOsparcVariableIdentifierError,
    raise_if_unresolved_osparc_variable_identifier_found,
    replace_osparc_variable_identifier,
)
from models_library.products import ProductName
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.service_settings_labels import ComposeSpecLabelDict
from models_library.services import ServiceKey, ServiceVersion
from models_library.services_types import ServiceRunID
from models_library.users import UserID
from models_library.utils.specs_substitution import SpecsSubstitutionsResolver
from pydantic import BaseModel
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from servicelib.logging_utils import log_context

from ...utils.db import get_repository
from ...utils.osparc_variables import (
    ContextDict,
    OsparcVariablesTable,
    resolve_variables_from_context,
)
from ..db.repositories.services_environments import ServicesEnvironmentsRepository
from ._api_auth import get_or_create_user_api_key, get_or_create_user_api_secret
from ._user import request_user_email, request_user_role

_logger = logging.getLogger(__name__)

TBaseModel = TypeVar("TBaseModel", bound=BaseModel)


async def substitute_vendor_secrets_in_model(
    app: FastAPI,
    model: TBaseModel,
    *,
    safe: bool = True,
    service_key: ServiceKey,
    service_version: ServiceVersion,
    product_name: ProductName,
) -> TBaseModel:
    result: TBaseModel = model
    try:
        with log_context(_logger, logging.DEBUG, "substitute_vendor_secrets_in_model"):
            # checks before to avoid unnecessary calls to pg
            # if it raises an error vars need replacement
            _logger.debug("model in which to replace model=%s", model)
            raise_if_unresolved_osparc_variable_identifier_found(model)
    except UnresolvedOsparcVariableIdentifierError as err:
        repo = get_repository(app, ServicesEnvironmentsRepository)
        vendor_secrets = await repo.get_vendor_secrets(
            service_key=service_key,
            service_version=service_version,
            product_name=product_name,
        )
        _logger.warning(
            "Failed to resolve osparc variable identifiers in model (%s). Replacing vendor secrets",
            err,
        )
        result = replace_osparc_variable_identifier(model, vendor_secrets)

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

        # resolve substitutions
        resolver.set_substitutions(mappings=vendor_secrets)
        new_specs: dict[str, Any] = resolver.run(safe=safe)
        return new_specs

    return deepcopy(specs)


class OsparcSessionVariablesTable(OsparcVariablesTable, SingletonInAppStateMixin):
    app_state_name: str = "session_variables_table"

    @classmethod
    def create(cls, app: FastAPI):
        table = cls()
        # Registers some session osparc_variables
        # WARNING: context_name needs to match session_context!
        # NOTE: please keep alphabetically ordered
        for name, context_name in [
            ("OSPARC_VARIABLE_NODE_ID", "node_id"),
            ("OSPARC_VARIABLE_PRODUCT_NAME", "product_name"),
            ("OSPARC_VARIABLE_STUDY_UUID", "project_id"),
            ("OSPARC_VARIABLE_SERVICE_RUN_ID", "run_id"),
            ("OSPARC_VARIABLE_USER_ID", "user_id"),
            ("OSPARC_VARIABLE_API_HOST", "api_server_base_url"),
        ]:
            table.register_from_context(name, context_name)

        table.register_from_handler("OSPARC_VARIABLE_USER_EMAIL")(request_user_email)
        table.register_from_handler("OSPARC_VARIABLE_USER_ROLE")(request_user_role)
        table.register_from_handler("OSPARC_VARIABLE_API_KEY")(
            get_or_create_user_api_key
        )
        table.register_from_handler("OSPARC_VARIABLE_API_SECRET")(
            get_or_create_user_api_secret
        )

        _logger.debug(
            "Registered session_variables_table=%s", sorted(table.variables_names())
        )
        table.set_to_app_state(app)
        return table


_NEW_ENVIRONMENTS: Final = {
    "OSPARC_API_BASE_URL": "$OSPARC_VARIABLE_API_HOST",
    "OSPARC_API_KEY": "$OSPARC_VARIABLE_API_KEY",
    "OSPARC_API_SECRET": "$OSPARC_VARIABLE_API_SECRET",
    "OSPARC_STUDY_ID": "$OSPARC_VARIABLE_STUDY_UUID",
    "OSPARC_NODE_ID": "$OSPARC_VARIABLE_NODE_ID",
}


def auto_inject_environments(
    compose_spec: ComposeSpecLabelDict,
) -> ComposeSpecLabelDict:
    # SEE https://github.com/ITISFoundation/osparc-simcore/issues/5925
    for service in compose_spec.get("services", {}).values():
        current_environment = deepcopy(service.get("environment", {}))

        # if _NEW_ENVIRONMENTS are already defined, then do not change them
        if isinstance(current_environment, dict):
            service["environment"] = {
                **_NEW_ENVIRONMENTS,
                **current_environment,
            }
        elif isinstance(current_environment, list):
            service["environment"] += [
                f"{name}={value}"
                for name, value in _NEW_ENVIRONMENTS.items()
                if not any(e.startswith(name) for e in current_environment)
            ]
    return compose_spec


async def resolve_and_substitute_session_variables_in_model(
    app: FastAPI,
    model: TBaseModel,
    *,
    safe: bool = True,
    user_id: UserID,
    product_name: str,
    project_id: ProjectID,
    node_id: NodeID,
    service_run_id: ServiceRunID,
) -> TBaseModel:
    result: TBaseModel = model
    try:
        with log_context(
            _logger, logging.DEBUG, "resolve_and_substitute_session_variables_in_model"
        ):
            # checks before to avoid unnecessary calls to pg
            # if it raises an error vars need replacement
            raise_if_unresolved_osparc_variable_identifier_found(model)
    except UnresolvedOsparcVariableIdentifierError:
        table = OsparcSessionVariablesTable.get_from_app_state(app)
        identifiers = await resolve_variables_from_context(
            table.copy(),
            context=ContextDict(
                app=app,
                user_id=user_id,
                product_name=product_name,
                project_id=project_id,
                node_id=node_id,
                run_id=service_run_id,
                api_server_base_url=app.state.settings.DIRECTOR_V2_PUBLIC_API_BASE_URL,
            ),
        )
        _logger.debug("replacing with the identifiers=%s", identifiers)
        result = replace_osparc_variable_identifier(model, identifiers)

    if not safe:
        raise_if_unresolved_osparc_variable_identifier_found(result)

    return result


async def resolve_and_substitute_session_variables_in_specs(
    app: FastAPI,
    specs: dict[str, Any],
    *,
    safe: bool = True,
    user_id: UserID,
    product_name: str,
    project_id: ProjectID,
    node_id: NodeID,
    service_run_id: ServiceRunID,
) -> dict[str, Any]:
    table = OsparcSessionVariablesTable.get_from_app_state(app)
    resolver = SpecsSubstitutionsResolver(specs, upgrade=False)

    if requested := set(resolver.get_identifiers()):
        available = set(table.variables_names())
        identifiers_to_replace = available.intersection(requested)
        _logger.debug(
            "resolve_and_substitute_session_variables_in_specs identifiers_to_replace=%s",
            identifiers_to_replace,
        )
        if identifiers_to_replace:
            environs = await resolve_variables_from_context(
                table.copy(include=identifiers_to_replace),
                context=ContextDict(
                    app=app,
                    user_id=user_id,
                    product_name=product_name,
                    project_id=project_id,
                    node_id=node_id,
                    run_id=service_run_id,
                    api_server_base_url=app.state.settings.DIRECTOR_V2_PUBLIC_API_BASE_URL,
                ),
            )

            resolver.set_substitutions(mappings=environs)
            new_specs: dict[str, Any] = resolver.run(safe=safe)
            return new_specs

    return deepcopy(specs)


def setup(app: FastAPI):
    """
    **o2sparc variables and secrets** are identifiers-value maps that are substituted on the service specs (e.g. docker-compose).
        - **vendor secrets**: information set by a vendor on the platform. e.g. a vendor service license
        - **session variables**: some session information as "current user email" or the "current product name"
        - **lifespan variables**: produced before a service is started and cleaned up after it finishes (e.g. API tokens )
    """
    app.add_event_handler(
        "startup", functools.partial(OsparcSessionVariablesTable.create, app)
    )


#
# CLI helpers
#


def list_osparc_session_variables() -> list[str]:
    app = FastAPI()
    table = OsparcSessionVariablesTable.create(app)
    return sorted(table.variables_names())
