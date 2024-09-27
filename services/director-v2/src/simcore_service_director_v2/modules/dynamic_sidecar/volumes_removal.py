from models_library.projects_nodes_io import NodeID
from servicelib.rabbitmq import RabbitMQClient
from servicelib.rabbitmq.rpc_interfaces.agent.volumes import (
    remove_volumes_without_backup_for_service,
)


async def remove_volumes_from_node(
    rabbitmq_client: RabbitMQClient,
    docker_node_id: str,
    swarm_stack_name: str,
    *,
    node_id: NodeID,
) -> None:
    """removes all service volumes form the node where it was running"""

    await remove_volumes_without_backup_for_service(
        rabbitmq_client,
        docker_node_id=docker_node_id,
        swarm_stack_name=swarm_stack_name,
        node_id=node_id,
    )
