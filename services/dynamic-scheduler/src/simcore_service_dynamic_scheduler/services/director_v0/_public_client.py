import logging
from typing import Any, cast

import httpx
from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services_service import (
    RunningDynamicServiceDetails,
)
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.service_settings_labels import SimcoreServiceLabels
from models_library.services_base import ServiceKeyVersion
from models_library.users import UserID
from pydantic import TypeAdapter
from servicelib.fastapi.app_state import SingletonInAppStateMixin

from ._thin_client import DirectorV0ThinClient

logger = logging.getLogger(__name__)


def _unenvelope_or_raise_error(resp: httpx.Response) -> dict | list:
    """
    Director responses are enveloped
    If successful response, we un-envelop it and return data as a dict
    If error, is detected raise an ValueError
    """
    body = resp.json()
    if "data" in body:
        return body["data"]  # type: ignore[no-any-return]

    msg = f"Unexpected, data was not returned: {body=}"
    raise ValueError(msg)


class DirectorV0PublicClient(SingletonInAppStateMixin):
    app_state_name: str = "director_v0_public_client"

    def __init__(self, app: FastAPI) -> None:
        self.app = app

    async def get_running_service_details(
        self, node_id: NodeID
    ) -> RunningDynamicServiceDetails:
        response = await DirectorV0ThinClient.get_from_app_state(
            self.app
        ).get_running_interactive_service_details(node_id)
        return TypeAdapter(RunningDynamicServiceDetails).validate_python(
            _unenvelope_or_raise_error(response)
        )

    async def get_service_labels(  # required
        self, service: ServiceKeyVersion
    ) -> SimcoreServiceLabels:
        response = await DirectorV0ThinClient.get_from_app_state(
            self.app
        ).get_services_labels(service)
        return TypeAdapter(SimcoreServiceLabels).validate_python(
            _unenvelope_or_raise_error(response)
        )

    async def get_running_services(  # required
        self, user_id: UserID | None = None, project_id: ProjectID | None = None
    ) -> list[RunningDynamicServiceDetails]:
        response = await DirectorV0ThinClient.get_from_app_state(
            self.app
        ).get_running_interactive_services(user_id=user_id, project_id=project_id)
        return [
            RunningDynamicServiceDetails(**x)
            for x in cast(list[dict[str, Any]], _unenvelope_or_raise_error(response))
        ]
