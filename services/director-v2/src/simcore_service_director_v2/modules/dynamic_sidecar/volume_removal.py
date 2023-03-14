from servicelib.rabbitmq_utils import RPCNamespace

from ..rabbitmq import RabbitMQClient


async def remove_volumes_from_node(
    rabbitmq_client: RabbitMQClient,
    volume_names: list[str],
    docker_node_id: str,
    *,
    volume_remove_timeout_s: float = 60,
    connection_error_timeout_s: float,
) -> None:
    """
    Starts a service at target docker node which will remove
    all entries in the `volumes_names` list.
    """

    namespace = RPCNamespace.from_entries(
        {"service": "agent", "docker_node_id": docker_node_id}
    )

    await rabbitmq_client.rpc_request(
        namespace=namespace,
        method_name="remove_volumes",
        volume_names=volume_names,
        volume_remove_timeout_s=volume_remove_timeout_s,
        timeout_s_method=volume_remove_timeout_s * 1.1,
        timeout_s_connection_error=connection_error_timeout_s,
    )
