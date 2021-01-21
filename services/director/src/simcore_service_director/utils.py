from typing import Dict
import aiodocker
from . import config, exceptions


async def get_swarm_network(client: aiodocker.docker.Docker) -> Dict:
    network_name = "_default"
    if config.SIMCORE_SERVICES_NETWORK_NAME:
        network_name = "{}".format(config.SIMCORE_SERVICES_NETWORK_NAME)
    # try to find the network name (usually named STACKNAME_default)
    networks = [
        x
        for x in (await client.networks.list())
        if "swarm" in x["Scope"] and network_name in x["Name"]
    ]
    if not networks or len(networks) > 1:
        raise exceptions.DirectorException(
            msg="Swarm network name is not configured, found following networks: {}".format(
                networks
            )
        )
    return networks[0]