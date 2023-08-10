# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable


# Selection of core and tool services started in this swarm fixture (integration)
from collections.abc import Callable
from typing import Final

import pytest
from fastapi import FastAPI
from pydantic import parse_obj_as
from servicelib.rabbitmq import RabbitMQClient
from servicelib.rabbitmq_utils import RPCMethodName, RPCNamespace

pytest_simcore_core_services_selection = [
    "rabbit",
]

pytest_simcore_ops_services_selection = []


@pytest.fixture
async def clusters_keeper_rabbitmq_rpc_client(
    rabbitmq_client: Callable[[str], RabbitMQClient]
) -> RabbitMQClient:
    rpc_client = rabbitmq_client("pytest_clusters_keeper_rpc_client")
    assert rpc_client
    await rpc_client.rpc_initialize()
    return rpc_client


CLUSTERS_KEEPER_NAMESPACE: Final[RPCNamespace] = parse_obj_as(
    RPCNamespace, "clusters-keeper"
)


async def test_create_cluster(
    docker_swarm: None,
    enabled_rabbitmq: None,
    aws_subnet_id: str,
    aws_security_group_id: str,
    aws_ami_id: str,
    aws_allowed_ec2_instance_type_names: list[str],
    mocked_redis_server: None,
    clusters_keeper_rabbitmq_rpc_client: RabbitMQClient,
    initialized_app: FastAPI,
):
    # send rabbitmq rpc to create_cluster
    await clusters_keeper_rabbitmq_rpc_client.rpc_request(
        CLUSTERS_KEEPER_NAMESPACE, RPCMethodName("create_cluster")
    )
    # wait for response
    # check we do have a new machine in AWS
