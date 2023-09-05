import dataclasses
import logging
from typing import Awaitable, Callable, TypeAlias

from fastapi import FastAPI
from models_library.generated_models.docker_rest_api import (
    Availability,
    Node,
    NodeState,
)

from ..core.errors import Ec2InvalidDnsNameError
from ..core.settings import get_application_settings
from ..models import AssociatedInstance, Cluster, EC2InstanceData
from ..utils import ec2, utils_docker
from ..utils.dynamic_scaling import (
    associate_ec2_instances_with_nodes,
    node_host_name_from_ec2_private_dns,
)
from ..utils.rabbitmq import post_autoscaling_status_message
from .docker import get_docker_client
from .ec2 import get_ec2_client

logger = logging.getLogger(__name__)


async def _analyze_current_cluster(app: FastAPI) -> Cluster:
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec

    # get current docker nodes (these are associated (active or drained) or disconnected)
    docker_nodes: list[Node] = await utils_docker.get_monitored_nodes(
        get_docker_client(app),
        node_labels=app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NODE_LABELS,
    )

    # get the EC2 instances we have
    existing_ec2_instances = await get_ec2_client(app).get_instances(
        app_settings.AUTOSCALING_EC2_INSTANCES,
        ec2.get_ec2_tags(app_settings),
    )

    terminated_ec2_instances = await get_ec2_client(app).get_instances(
        app_settings.AUTOSCALING_EC2_INSTANCES,
        ec2.get_ec2_tags(app_settings),
        state_names=["terminated"],
    )

    attached_ec2s, pending_ec2s = await associate_ec2_instances_with_nodes(
        docker_nodes, existing_ec2_instances
    )

    def _is_node_up_and_available(node: Node, availability: Availability) -> bool:
        assert node.Status  # nosec
        assert node.Spec  # nosec
        return bool(
            node.Status.State == NodeState.ready
            and node.Spec.Availability == availability
        )

    def _node_not_ready(node: Node) -> bool:
        assert node.Status  # nosec
        return bool(node.Status.State != NodeState.ready)

    all_drained_nodes = [
        i
        for i in attached_ec2s
        if _is_node_up_and_available(i.node, Availability.drain)
    ]

    cluster = Cluster(
        active_nodes=[
            i
            for i in attached_ec2s
            if _is_node_up_and_available(i.node, Availability.active)
        ],
        drained_nodes=all_drained_nodes[
            app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER :
        ],
        reserve_drained_nodes=all_drained_nodes[
            : app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER
        ],
        pending_ec2s=pending_ec2s,
        terminated_instances=terminated_ec2_instances,
        disconnected_nodes=[n for n in docker_nodes if _node_not_ready(n)],
    )
    logger.info("current state: %s", f"{cluster=}")
    return cluster


async def _cleanup_disconnected_nodes(app: FastAPI, cluster: Cluster) -> Cluster:
    await utils_docker.remove_nodes(get_docker_client(app), cluster.disconnected_nodes)
    return dataclasses.replace(cluster, disconnected_nodes=[])


async def _try_attach_pending_ec2s(app: FastAPI, cluster: Cluster) -> Cluster:
    """label the drained instances that connected to the swarm which are missing the monitoring labels"""
    new_found_instances: list[AssociatedInstance] = []
    still_pending_ec2s: list[EC2InstanceData] = []
    app_settings = get_application_settings(app)
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    for instance_data in cluster.pending_ec2s:
        try:
            node_host_name = node_host_name_from_ec2_private_dns(instance_data)
            if new_node := await utils_docker.find_node_with_name(
                get_docker_client(app), node_host_name
            ):
                # it is attached, let's label it, but keep it as drained
                new_node = await utils_docker.tag_node(
                    get_docker_client(app),
                    new_node,
                    tags=utils_docker.get_docker_tags(app_settings),
                    available=False,
                )
                new_found_instances.append(AssociatedInstance(new_node, instance_data))
            else:
                still_pending_ec2s.append(instance_data)
        except Ec2InvalidDnsNameError:
            logger.exception("Unexpected EC2 private dns")
    # NOTE: first provision the reserve drained nodes if possible
    all_drained_nodes = (
        cluster.drained_nodes + cluster.reserve_drained_nodes + new_found_instances
    )
    return dataclasses.replace(
        cluster,
        drained_nodes=all_drained_nodes[
            app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER :
        ],
        reserve_drained_nodes=all_drained_nodes[
            : app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_MACHINES_BUFFER
        ],
        pending_ec2s=still_pending_ec2s,
    )


ScaleClusterCB: TypeAlias = Callable[[FastAPI, Cluster], Awaitable[Cluster]]


async def auto_scale_cluster(*, app: FastAPI, scale_cluster_cb: ScaleClusterCB) -> None:
    """Check that there are no pending tasks requiring additional resources in the cluster (docker swarm)
    If there are such tasks, this method will allocate new machines in AWS to cope with
    the additional load.
    """

    cluster = await _analyze_current_cluster(app)
    cluster = await _cleanup_disconnected_nodes(app, cluster)
    cluster = await _try_attach_pending_ec2s(app, cluster)
    cluster = await scale_cluster_cb(app, cluster)

    # inform on rabbit about status
    await post_autoscaling_status_message(app, cluster)
