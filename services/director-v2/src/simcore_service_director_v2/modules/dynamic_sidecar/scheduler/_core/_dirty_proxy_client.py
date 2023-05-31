from typing import Any

import httpx
from models_library.basic_types import PortInt
from models_library.projects_nodes import NodeID


def _get_request_data(
    entrypoint_container_name: str, service_port: PortInt
) -> dict[str, Any]:
    return {
        # NOTE: the admin endpoint is not present any more.
        # This avoids user services from being able to access it.
        "apps": {
            "http": {
                "servers": {
                    "userservice": {
                        "listen": ["0.0.0.0:80"],
                        "routes": [
                            {
                                "handle": [
                                    {
                                        "handler": "reverse_proxy",
                                        "upstreams": [
                                            {
                                                "dial": f"{entrypoint_container_name}:{service_port}"
                                            }
                                        ],
                                    }
                                ]
                            }
                        ],
                    }
                }
            }
        },
    }


async def configure_proxy(
    node_id: NodeID,
    admin_api_port: PortInt,
    entrypoint_container_name: str,
    service_port: PortInt,
) -> None:
    url = f"http://dy-proxy_{node_id}:{admin_api_port}/load"
    request_data = _get_request_data(entrypoint_container_name, service_port)
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=request_data)
        if response.status_code != 200:
            raise RuntimeError(
                f"While requesting '{url}' with '{request_data}' an error was raised: '{response.text}'"
            )
