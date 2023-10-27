# pylint: disable=redefined-outer-name
# pylint: disable=unused-argument
# pylint: disable=unused-variable

import pytest
from fastapi import FastAPI
from models_library.rpc_schemas_clusters_keeper.clusters import EC2InstanceType
from servicelib.rabbitmq import RabbitMQRPCClient, RPCMethodName, RPCNamespace

pytest_simcore_core_services_selection = [
    "rabbit",
]

pytest_simcore_ops_services_selection = []


@pytest.fixture
def _base_configuration(
    docker_swarm: None,
    enabled_rabbitmq: None,
    aws_subnet_id: str,
    aws_security_group_id: str,
    aws_ami_id: str,
    aws_allowed_ec2_instance_type_names: list[str],
    mocked_redis_server: None,
    initialized_app: FastAPI,
) -> None:
    ...


async def test_get_instance_type_details_all_options(
    _base_configuration: None,
    clusters_keeper_namespace: RPCNamespace,
    clusters_keeper_rabbitmq_rpc_client: RabbitMQRPCClient,
):
    # an empty set returns all options
    rpc_response = await clusters_keeper_rabbitmq_rpc_client.request(
        clusters_keeper_namespace,
        RPCMethodName("get_instance_type_details"),
        instance_type_names=set(),
    )
    assert rpc_response
    assert isinstance(rpc_response, list)
    assert isinstance(rpc_response[0], EC2InstanceType)


async def test_get_instance_type_details_specific_type_names(
    _base_configuration: None,
    clusters_keeper_namespace: RPCNamespace,
    clusters_keeper_rabbitmq_rpc_client: RabbitMQRPCClient,
):
    # an empty set returns all options
    rpc_response = await clusters_keeper_rabbitmq_rpc_client.request(
        clusters_keeper_namespace,
        RPCMethodName("get_instance_type_details"),
        instance_type_names={"t2.micro", "g4dn.xlarge"},
    )
    assert rpc_response
    assert isinstance(rpc_response, list)
    assert len(rpc_response) == 2
    assert rpc_response[0].name == "g4dn.xlarge"
    assert rpc_response[1].name == "t2.micro"
