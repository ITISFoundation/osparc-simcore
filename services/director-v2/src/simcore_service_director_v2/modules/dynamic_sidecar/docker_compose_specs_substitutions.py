from copy import deepcopy
from typing import Any, Callable, Mapping

from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services import ServiceKey
from models_library.users import UserID
from models_library.utils.specs_substitution import SpecsEnvironmentsResolver

from ...utils.db import get_repository
from ..db.repositories.services_environments import ServicesEnvironmentsRepository


async def substitute_vendor_environments(
    app: FastAPI,
    compose_spec: dict[str, Any],
    service_key: ServiceKey,
) -> dict[str, Any]:
    specs_resolver = SpecsEnvironmentsResolver(compose_spec, upgrade=False)
    repo = get_repository(app, ServicesEnvironmentsRepository)

    if any(
        repo.is_vendor_secret_identifier(idr)
        for idr in specs_resolver.get_identifiers()
    ):
        # checks before to avoid unnecesary calls to pg
        vendor_secrets = await repo.get_vendor_secrets(service_key=service_key)

        # resolve substitutions
        specs_resolver.set_substitutions(environs=vendor_secrets)
        new_compose_spec = specs_resolver.run()
        return new_compose_spec

    return deepcopy(compose_spec)


async def substitute_session_environments(
    app: FastAPI,
    compose_spec: dict[str, Any],
    user_id: UserID,
    product_name: str,
    project_uuid: ProjectID,
    node_uuid: NodeID,
):
    assert app  # nosec
    assert user_id  # nosec

    specs_resolver = SpecsEnvironmentsResolver(compose_spec, upgrade=False)

    # TODO: listing of all published session oenvs
    environs = {
        "OSPARC_ENVIRONMENT_PRODUCT_NAME": product_name,
        "OSPARC_ENVIRONMENT_STUDY_UUID": project_uuid,
        "OSPARC_ENVIRONMENT_NODE_UUID": node_uuid,
        # TODO: might include in the resolver to execute the callback!!
        # TODO: "OSPARC_ENVIRONMENT_USER_EMAIL": request_user_email(app, user_id),
        # TODO: "OSPARC_ENVIRONMENT_USER_ROLE": request_user_role(app, user_id),
    }

    specs_resolver.set_substitutions(environs=environs)
    new_compose_spec = specs_resolver.run()
    return new_compose_spec


async def substitute_request_environments(
    _app: FastAPI,
    _pod_compose_spec: dict[str, Any],
    _callbacks_registry: Mapping[str, Callable],
):
    raise NotImplementedError()
