import logging
from typing import Any, cast

from fastapi import FastAPI, status
from httpx import Response
from models_library.api_schemas_webserver.projects_nodes import NodeGet
from models_library.projects import ProjectID
from models_library.projects_nodes_io import NodeID
from models_library.users import UserID
from pydantic import TypeAdapter
from servicelib.fastapi.app_state import SingletonInAppStateMixin
from servicelib.fastapi.http_client_thin import UnexpectedStatusError

from ._thin_client import DirectorV0ThinClient

logger = logging.getLogger(__name__)


def _unenvelope_or_raise_error(resp: Response) -> dict | list:
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

    async def get_running_service_details(self, node_id: NodeID) -> NodeGet | None:
        try:
            response = await DirectorV0ThinClient.get_from_app_state(self.app).get_running_interactive_service_details(
                node_id
            )
            return TypeAdapter(NodeGet).validate_python(_unenvelope_or_raise_error(response))
        except UnexpectedStatusError as err:
            if err.response.status_code == status.HTTP_404_NOT_FOUND:  # type: ignore[attr-defined] # pylint: disable=no-member # type: ignore
                return None
            raise

    async def get_running_services(
        self, user_id: UserID | None = None, project_id: ProjectID | None = None
    ) -> list[NodeGet]:
        response = await DirectorV0ThinClient.get_from_app_state(self.app).get_running_interactive_services(
            user_id=user_id, project_id=project_id
        )
        return [NodeGet(**x) for x in cast(list[dict[str, Any]], _unenvelope_or_raise_error(response))]
