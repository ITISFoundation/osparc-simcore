from copy import deepcopy
from typing import Any, Callable, Mapping

from fastapi import FastAPI
from models_library.services import ServiceKey
from models_library.users import UserID
from models_library.utils.docker_compose import SpecsEnvironmentsResolver

from ...utils.db import get_repository
from ..db.repositories.services_specifications import ServicesSpecificationsRepository


async def substitute_vendor_environments(
    app: FastAPI,
    pod_compose_spec: dict[str, Any],
    service_key: ServiceKey,
) -> dict[str, Any]:
    specs_resolver = SpecsEnvironmentsResolver(pod_compose_spec, upgrade=False)

    if any(
        idr.startswith("OSPARC_ENVIRONMENT_")
        for idr in specs_resolver.get_identifiers()
    ):
        repo = get_repository(app, ServicesSpecificationsRepository)
        vendor_environments = await repo.get_vendor_environments(
            service_key=service_key
        )

        specs_resolver.set_substitutions(environs=vendor_environments)
        new_pod_compose_spec = specs_resolver.run()
    else:
        new_pod_compose_spec = deepcopy(pod_compose_spec)
    return new_pod_compose_spec


async def substitute_session_environments(
    _app: FastAPI,
    _pod_compose_spec: dict[str, Any],
    _user_id: UserID,
    _product_name: str,
):
    raise NotImplementedError()


async def substitute_request_environments(
    _app: FastAPI,
    _pod_compose_spec: dict[str, Any],
    _callbacks_registry: Mapping[str, Callable],
):
    raise NotImplementedError()
