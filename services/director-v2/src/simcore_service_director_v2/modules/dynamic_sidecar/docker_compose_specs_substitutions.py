from copy import deepcopy
from typing import Any, Callable, Mapping

from fastapi import FastAPI
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.services import ServiceKey
from models_library.users import UserID
from models_library.utils.docker_compose import SpecsEnvironmentsResolver

from ...utils.db import get_repository
from ..db.repositories.services_specifications import ServicesSpecificationsRepository


async def substitute_vendor_environments(
    app: FastAPI,
    compose_spec: dict[str, Any],
    service_key: ServiceKey,
) -> dict[str, Any]:
    specs_resolver = SpecsEnvironmentsResolver(compose_spec, upgrade=False)

    # TODO: define OSPARC_ENVIRONMENT_VENDOR_ once!
    if any(
        idr.startswith("OSPARC_ENVIRONMENT_VENDOR_")
        for idr in specs_resolver.get_identifiers()
    ):
        repo = get_repository(app, ServicesSpecificationsRepository)
        vendor_environments = await repo.get_vendor_environments(
            service_key=service_key
        )

        specs_resolver.set_substitutions(environs=vendor_environments)
        new_compose_spec = specs_resolver.run()
    else:
        new_compose_spec = deepcopy(compose_spec)
    return new_compose_spec


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

    # TODO: listing of all session envs.
    environs = {
        "OSPARC_ENVIRONMENT_PRODUCT_NAME": product_name,
        "OSPARC_ENVIRONMENT_STUDY_UUID": project_uuid,
        "OSPARC_ENVIRONMENT_NODE_UUID": node_uuid,
        # TODO: "OSPARC_ENVIRONMENT_USER_EMAIL": request_user_email(app, user_id),
    }

    specs_resolver.set_substitutions(environs=environs)
    new_pod_compose_spec = specs_resolver.run()
    return new_pod_compose_spec


async def substitute_request_environments(
    _app: FastAPI,
    _pod_compose_spec: dict[str, Any],
    _callbacks_registry: Mapping[str, Callable],
):
    raise NotImplementedError()
