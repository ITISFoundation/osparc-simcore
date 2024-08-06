import base64
from collections.abc import Sequence

from models_library.docker import DockerGenericTag
from models_library.utils.json_serialization import json_dumps
from types_aiobotocore_ec2 import EC2Client
from types_aiobotocore_ec2.literals import InstanceStateNameType, InstanceTypeType
from types_aiobotocore_ec2.type_defs import FilterTypeDef, InstanceTypeDef, TagTypeDef


async def assert_autoscaled_computational_ec2_instances(
    ec2_client: EC2Client,
    *,
    expected_num_reservations: int,
    expected_num_instances: int,
    expected_instance_type: InstanceTypeType,
    expected_instance_state: InstanceStateNameType,
    expected_additional_tag_keys: list[str],
) -> list[InstanceTypeDef]:
    return await assert_ec2_instances(
        ec2_client,
        expected_num_reservations=expected_num_reservations,
        expected_num_instances=expected_num_instances,
        expected_instance_type=expected_instance_type,
        expected_instance_state=expected_instance_state,
        expected_instance_tag_keys=[
            "io.simcore.autoscaling.dask-scheduler_url",
            "user_id",
            "wallet_id",
            *expected_additional_tag_keys,
        ],
        expected_user_data=["docker swarm join"],
    )


async def assert_autoscaled_dynamic_ec2_instances(
    ec2_client: EC2Client,
    *,
    expected_num_reservations: int,
    expected_num_instances: int,
    expected_instance_type: InstanceTypeType,
    expected_instance_state: InstanceStateNameType,
    expected_additional_tag_keys: list[str],
    instance_filters: Sequence[FilterTypeDef] | None,
) -> list[InstanceTypeDef]:
    return await assert_ec2_instances(
        ec2_client,
        expected_num_reservations=expected_num_reservations,
        expected_num_instances=expected_num_instances,
        expected_instance_type=expected_instance_type,
        expected_instance_state=expected_instance_state,
        expected_instance_tag_keys=[
            "io.simcore.autoscaling.monitored_nodes_labels",
            "io.simcore.autoscaling.monitored_services_labels",
            *expected_additional_tag_keys,
        ],
        expected_user_data=["docker swarm join"],
        instance_filters=instance_filters,
    )


async def assert_autoscaled_dynamic_warm_pools_ec2_instances(
    ec2_client: EC2Client,
    *,
    expected_num_reservations: int,
    expected_num_instances: int,
    expected_instance_type: InstanceTypeType,
    expected_instance_state: InstanceStateNameType,
    expected_additional_tag_keys: list[str],
    expected_pre_pulled_images: list[DockerGenericTag] | None,
    instance_filters: Sequence[FilterTypeDef] | None,
) -> list[InstanceTypeDef]:
    return await assert_ec2_instances(
        ec2_client,
        expected_num_reservations=expected_num_reservations,
        expected_num_instances=expected_num_instances,
        expected_instance_type=expected_instance_type,
        expected_instance_state=expected_instance_state,
        expected_instance_tag_keys=[
            "io.simcore.autoscaling.monitored_nodes_labels",
            "io.simcore.autoscaling.monitored_services_labels",
            "io.simcore.autoscaling.buffer_machine",
            *expected_additional_tag_keys,
        ],
        expected_pre_pulled_images=expected_pre_pulled_images,
        expected_user_data=[],
        instance_filters=instance_filters,
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
    expected_pre_pulled_images: list[DockerGenericTag] | None = None,
    instance_filters: Sequence[FilterTypeDef] | None = None,
) -> list[InstanceTypeDef]:
    list_instances: list[InstanceTypeDef] = []
    all_instances = await ec2_client.describe_instances(Filters=instance_filters or [])
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
            expected_tag_keys = {
                *expected_instance_tag_keys,
                "io.simcore.autoscaling.version",
                "Name",
            }
            instance_tag_keys = {tag["Key"] for tag in instance["Tags"] if "Key" in tag}
            assert instance_tag_keys == expected_tag_keys

            if expected_pre_pulled_images is None:
                assert (
                    "io.simcore.autoscaling.pre_pulled_images" not in instance_tag_keys
                )
            else:
                assert "io.simcore.autoscaling.pre_pulled_images" in instance_tag_keys

                def _by_pre_pull_image(ec2_tag: TagTypeDef) -> bool:
                    assert "Key" in ec2_tag
                    return ec2_tag["Key"] == "io.simcore.autoscaling.pre_pulled_images"

                instance_pre_pulled_images_aws_tag = next(
                    iter(filter(_by_pre_pull_image, instance["Tags"]))
                )
                assert "Value" in instance_pre_pulled_images_aws_tag
                assert (
                    instance_pre_pulled_images_aws_tag["Value"]
                    == f"{json_dumps(expected_pre_pulled_images)}"
                )

            assert "PrivateDnsName" in instance
            instance_private_dns_name = instance["PrivateDnsName"]
            if expected_instance_state not in ["terminated"]:
                # NOTE: moto behaves here differently than AWS by still returning an IP which does not really make sense
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
