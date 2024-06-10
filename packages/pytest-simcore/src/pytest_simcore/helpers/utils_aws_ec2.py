import base64

from types_aiobotocore_ec2 import EC2Client
from types_aiobotocore_ec2.literals import InstanceStateNameType, InstanceTypeType
from types_aiobotocore_ec2.type_defs import InstanceTypeDef


async def assert_autoscaled_computational_ec2_instances(
    ec2_client: EC2Client,
    *,
    num_reservations: int,
    num_instances: int,
    instance_type: InstanceTypeType,
    instance_state: InstanceStateNameType,
) -> list[InstanceTypeDef]:
    return await assert_ec2_instances(
        ec2_client,
        expected_num_reservations=num_reservations,
        expected_num_instances=num_instances,
        expected_instance_type=instance_type,
        expected_instance_state=instance_state,
        expected_instance_tag_keys=[
            "io.simcore.autoscaling.dask-scheduler_url",
        ],
        expected_user_data=["docker swarm join"],
    )


async def assert_autoscaled_dynamic_ec2_instances(
    ec2_client: EC2Client,
    *,
    num_reservations: int,
    num_instances: int,
    instance_type: InstanceTypeType,
    instance_state: InstanceStateNameType,
) -> list[InstanceTypeDef]:
    return await assert_ec2_instances(
        ec2_client,
        expected_num_reservations=num_reservations,
        expected_num_instances=num_instances,
        expected_instance_type=instance_type,
        expected_instance_state=instance_state,
        expected_instance_tag_keys=[
            "io.simcore.autoscaling.monitored_nodes_labels",
            "io.simcore.autoscaling.monitored_services_labels",
        ],
        expected_user_data=["docker swarm join"],
    )


async def assert_autoscaled_dynamic_warm_pools_ec2_instances(
    ec2_client: EC2Client,
    *,
    num_reservations: int,
    num_instances: int,
    instance_type: InstanceTypeType,
    instance_state: InstanceStateNameType,
) -> list[InstanceTypeDef]:
    return await assert_ec2_instances(
        ec2_client,
        expected_num_reservations=num_reservations,
        expected_num_instances=num_instances,
        expected_instance_type=instance_type,
        expected_instance_state=instance_state,
        expected_instance_tag_keys=[
            "io.simcore.autoscaling.monitored_nodes_labels",
            "io.simcore.autoscaling.monitored_services_labels",
            "buffer-machine",
        ],
        expected_user_data=[],
    )


async def assert_ec2_instances(
    ec2_client: EC2Client,
    *,
    expected_num_reservations: int,
    expected_num_instances: int,
    expected_instance_type: InstanceTypeType,
    expected_instance_state: InstanceStateNameType,
    expected_instance_tag_keys: list[str],
    expected_user_data: list[str],
) -> list[InstanceTypeDef]:
    list_instances: list[InstanceTypeDef] = []
    all_instances = await ec2_client.describe_instances()
    assert len(all_instances["Reservations"]) == expected_num_reservations
    for reservation in all_instances["Reservations"]:
        assert "Instances" in reservation
        assert (
            len(reservation["Instances"]) == expected_num_instances
        ), f"expected {expected_num_instances}, found {len(reservation['Instances'])}"
        for instance in reservation["Instances"]:
            assert "InstanceType" in instance
            assert instance["InstanceType"] == expected_instance_type
            assert "Tags" in instance
            assert instance["Tags"]
            expected_tag_keys = [
                *expected_instance_tag_keys,
                "io.simcore.autoscaling.version",
                "Name",
                "user_id",
                "wallet_id",
                "osparc-tag",
            ]
            for tag_dict in instance["Tags"]:
                assert "Key" in tag_dict
                assert "Value" in tag_dict

                assert tag_dict["Key"] in expected_tag_keys
            assert "PrivateDnsName" in instance
            instance_private_dns_name = instance["PrivateDnsName"]
            assert instance_private_dns_name.endswith(".ec2.internal")
            assert "State" in instance
            state = instance["State"]
            assert "Name" in state
            assert state["Name"] == expected_instance_state

            assert "InstanceId" in instance
            user_data = await ec2_client.describe_instance_attribute(
                Attribute="userData", InstanceId=instance["InstanceId"]
            )
            assert "UserData" in user_data
            assert "Value" in user_data["UserData"]
            user_data = base64.b64decode(user_data["UserData"]["Value"]).decode()
            for user_data_string in expected_user_data:
                assert user_data.count(user_data_string) == 1
            list_instances.append(instance)
    return list_instances
