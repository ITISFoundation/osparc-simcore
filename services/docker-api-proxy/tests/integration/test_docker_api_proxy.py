import json
import sys
from pathlib import Path

from servicelib.docker_utils import get_remote_docker_client
from settings_library.docker_api_proxy import DockerApiProxysettings

HERE = Path(sys.argv[0] if __name__ == "__main__" else __file__).resolve().parent

pytest_simcore_core_services_selection = [
    "docker-api-proxy",
]


async def test_unauthenticated(docker_api_proxy_settings: DockerApiProxysettings):
    docker = await get_remote_docker_client(docker_api_proxy_settings)
    async with docker:
        info = await docker.system.info()
        print(json.dumps(info, indent=2))
