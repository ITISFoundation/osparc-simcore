from collections.abc import Callable

import arrow
from aws_library.ec2 import EC2InstanceData
from models_library.generated_models.docker_rest_api import (
    Availability,
    Node,
    NodeState,
)
from pytest_mock import MockType
from simcore_service_autoscaling.models import AssociatedInstance, Cluster
from simcore_service_autoscaling.utils.utils_docker import (
    _OSPARC_NODE_TERMINATION_PROCESS_LABEL_KEY,
    _OSPARC_SERVICE_READY_LABEL_KEY,
    _OSPARC_SERVICES_READY_DATETIME_LABEL_KEY,
)


def assert_cluster_state(
    spied_cluster_analysis: MockType, *, expected_calls: int, expected_num_machines: int
) -> Cluster:
    assert spied_cluster_analysis.call_count == expected_calls

    assert isinstance(spied_cluster_analysis.spy_return, Cluster)
    assert (
        spied_cluster_analysis.spy_return.total_number_of_machines()
        == expected_num_machines
    )
    print("current cluster state:", spied_cluster_analysis.spy_return)
    cluster = spied_cluster_analysis.spy_return
    spied_cluster_analysis.reset_mock()
    return cluster


def create_fake_association(
    create_fake_node: Callable[..., Node],
    drained_machine_id: str | None,
    terminating_machine_id: str | None,
):
    fake_node_to_instance_map = {}

    def _fake_node_creator(
        _nodes: list[Node], ec2_instances: list[EC2InstanceData]
    ) -> tuple[list[AssociatedInstance], list[EC2InstanceData]]:
        def _create_fake_node_with_labels(instance: EC2InstanceData) -> Node:
            if instance not in fake_node_to_instance_map:
                fake_node = create_fake_node()
                assert fake_node.spec
                fake_node.spec.availability = Availability.active
                assert fake_node.status
                fake_node.status.state = NodeState.ready
                assert fake_node.spec.labels
                fake_node.spec.labels |= {
                    _OSPARC_SERVICES_READY_DATETIME_LABEL_KEY: arrow.utcnow().isoformat(),
                    _OSPARC_SERVICE_READY_LABEL_KEY: (
                        "true" if instance.id != drained_machine_id else "false"
                    ),
                }
                if instance.id == terminating_machine_id:
                    fake_node.spec.labels |= {
                        _OSPARC_NODE_TERMINATION_PROCESS_LABEL_KEY: arrow.utcnow().isoformat()
                    }
                fake_node_to_instance_map[instance] = fake_node
            return fake_node_to_instance_map[instance]

        associated_instances = [
            AssociatedInstance(node=_create_fake_node_with_labels(i), ec2_instance=i)
            for i in ec2_instances
        ]

        return associated_instances, []

    return _fake_node_creator
