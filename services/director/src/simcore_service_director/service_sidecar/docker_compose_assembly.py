MOCK_COMPOSE_SPEC = """
version: "3.7"
services:
  whocontainer:
    image: "containous/whoami"
"""


async def assemble_spec(service_key: str, service_tag: str) -> str:
    """returns a docker-compose spec which will be use by the service-sidecar to start the service """
    return MOCK_COMPOSE_SPEC