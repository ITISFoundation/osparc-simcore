import aiodocker


async def ensure_network_cleanup(
    docker_client: aiodocker.Docker, project_id: str
) -> None:
    network_names = {x["Name"] for x in await docker_client.networks.list()}

    for network_name in network_names:
        if project_id in network_name:
            network = await docker_client.networks.get(network_name)
            try:
                # if there is an error this cleansup the environament
                # useful for development, avoids leaving too many
                # hanging networks
                delete_result = await network.delete()
                assert delete_result is True
            except aiodocker.exceptions.DockerError as e:
                # if the tests succeeds the network will nto exists
                str_error = str(e)
                assert "network" in str_error
                assert "not found" in str_error
