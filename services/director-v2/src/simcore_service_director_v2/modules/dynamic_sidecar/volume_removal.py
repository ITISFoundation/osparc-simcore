from servicelib.rabbitmq_utils import RPCNamespace

from ..rabbitmq import RabbitMQClient


async def remove_volumes_from_node(
    rabbitmq_client: RabbitMQClient,
    volume_names: list[str],
    docker_node_id: str,
    *,
    volume_removal_attempts: int = 15,
    sleep_between_attempts_s: int = 2
) -> None:
    """
    Starts a service at target docker node which will remove
    all entries in the `volumes_names` list.
    """

    namespace = RPCNamespace.from_entries(
        {"service": "agent", "docker_node_id": docker_node_id}
    )

    # Timeout for the runtime of the service is calculated based on the amount
    # of attempts required to remove each individual volume.
    # Volume removal is ran in parallel (adding 10% extra padding)
    volume_removal_timeout_s = volume_removal_attempts * sleep_between_attempts_s * 1.1

    await rabbitmq_client.rpc_request(
        namespace,
        "remove_volumes",
        volume_names=volume_names,
        volume_removal_attempts=volume_removal_attempts,
        sleep_between_attempts_s=sleep_between_attempts_s,
        timeout_s=volume_removal_timeout_s,
    )
