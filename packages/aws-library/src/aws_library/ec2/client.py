import contextlib
import logging
from dataclasses import dataclass
from typing import cast

import aioboto3
import botocore.exceptions
from aiobotocore.session import ClientCreatorContext
from aiocache import cached
from pydantic import ByteSize, parse_obj_as
from servicelib.logging_utils import log_context
from settings_library.ec2 import EC2Settings
from types_aiobotocore_ec2 import EC2Client
from types_aiobotocore_ec2.literals import InstanceStateNameType, InstanceTypeType
from types_aiobotocore_ec2.type_defs import FilterTypeDef

from .errors import (
    EC2InstanceNotFoundError,
    EC2InstanceTypeInvalidError,
    EC2RuntimeError,
    EC2TooManyInstancesError,
)
from .models import (
    EC2InstanceConfig,
    EC2InstanceData,
    EC2InstanceType,
    EC2Tags,
    Resources,
)
from .utils import compose_user_data

_logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SimcoreEC2API:
    client: EC2Client
    session: aioboto3.Session
    exit_stack: contextlib.AsyncExitStack

    @classmethod
    async def create(cls, settings: EC2Settings) -> "SimcoreEC2API":
        session = aioboto3.Session()
        session_client = session.client(
            "ec2",
            endpoint_url=settings.EC2_ENDPOINT,
            aws_access_key_id=settings.EC2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.EC2_SECRET_ACCESS_KEY,
            region_name=settings.EC2_REGION_NAME,
        )
        assert isinstance(session_client, ClientCreatorContext)  # nosec
        exit_stack = contextlib.AsyncExitStack()
        ec2_client = cast(
            EC2Client, await exit_stack.enter_async_context(session_client)
        )
        return cls(ec2_client, session, exit_stack)

    async def close(self) -> None:
        await self.exit_stack.aclose()

    async def ping(self) -> bool:
        try:
            await self.client.describe_account_attributes()
            return True
        except Exception:  # pylint: disable=broad-except
            return False

    @cached(noself=True)
    async def get_ec2_instance_capabilities(
        self,
        instance_type_names: set[InstanceTypeType],
    ) -> list[EC2InstanceType]:
        """returns the ec2 instance types from a list of instance type names
            NOTE: the order might differ!
        Arguments:
            instance_type_names -- the types to filter with

        Raises:
            Ec2InstanceTypeInvalidError: some invalid types were used as filter
            ClustersKeeperRuntimeError: unexpected error communicating with EC2

        """
        try:
            instance_types = await self.client.describe_instance_types(
                InstanceTypes=list(instance_type_names)
            )
            list_instances: list[EC2InstanceType] = []
            for instance in instance_types.get("InstanceTypes", []):
                with contextlib.suppress(KeyError):
                    list_instances.append(
                        EC2InstanceType(
                            name=instance["InstanceType"],
                            cpus=instance["VCpuInfo"]["DefaultVCpus"],
                            ram=ByteSize(
                                int(instance["MemoryInfo"]["SizeInMiB"]) * 1024 * 1024
                            ),
                        )
                    )
            return list_instances
        except botocore.exceptions.ClientError as exc:
            if exc.response.get("Error", {}).get("Code", "") == "InvalidInstanceType":
                raise EC2InstanceTypeInvalidError from exc
            raise EC2RuntimeError from exc  # pragma: no cover

    async def start_aws_instance(
        self,
        instance_config: EC2InstanceConfig,
        number_of_instances: int,
        max_number_of_instances: int = 10,
    ) -> list[EC2InstanceData]:
        with log_context(
            _logger,
            logging.INFO,
            msg=f"launching {number_of_instances} AWS instance(s) {instance_config.type.name} with {instance_config.tags=}",
        ):
            # first check the max amount is not already reached
            current_instances = await self.get_instances(
                key_names=[instance_config.key_name], tags=instance_config.tags
            )
            if len(current_instances) + number_of_instances > max_number_of_instances:
                raise EC2TooManyInstancesError(num_instances=max_number_of_instances)

            instances = await self.client.run_instances(
                ImageId=instance_config.ami_id,
                MinCount=number_of_instances,
                MaxCount=number_of_instances,
                InstanceType=instance_config.type.name,
                InstanceInitiatedShutdownBehavior="terminate",
                KeyName=instance_config.key_name,
                TagSpecifications=[
                    {
                        "ResourceType": "instance",
                        "Tags": [
                            {"Key": tag_key, "Value": tag_value}
                            for tag_key, tag_value in instance_config.tags.items()
                        ],
                    }
                ],
                UserData=compose_user_data(instance_config.startup_script),
                NetworkInterfaces=[
                    {
                        "AssociatePublicIpAddress": True,
                        "DeviceIndex": 0,
                        "SubnetId": instance_config.subnet_id,
                        "Groups": instance_config.security_group_ids,
                    }
                ],
            )
            instance_ids = [i["InstanceId"] for i in instances["Instances"]]
            _logger.info(
                "New instances launched: %s, waiting for them to start now...",
                instance_ids,
            )

            # wait for the instance to be in a pending state
            # NOTE: reference to EC2 states https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html
            waiter = self.client.get_waiter("instance_exists")
            await waiter.wait(InstanceIds=instance_ids)
            _logger.info("instances %s exists now.", instance_ids)

            # get the private IPs
            instances = await self.client.describe_instances(InstanceIds=instance_ids)
            instance_datas = [
                EC2InstanceData(
                    launch_time=instance["LaunchTime"],
                    id=instance["InstanceId"],
                    aws_private_dns=instance["PrivateDnsName"],
                    aws_public_ip=instance["PublicIpAddress"]
                    if "PublicIpAddress" in instance
                    else None,
                    type=instance["InstanceType"],
                    state=instance["State"]["Name"],
                    tags=parse_obj_as(
                        EC2Tags, {tag["Key"]: tag["Value"] for tag in instance["Tags"]}
                    ),
                    resources=Resources(
                        cpus=instance_config.type.cpus, ram=instance_config.type.ram
                    ),
                )
                for instance in instances["Reservations"][0]["Instances"]
            ]
            _logger.info(
                "%s is available, happy computing!!",
                f"{instance_datas=}",
            )
            return instance_datas

    async def get_instances(
        self,
        *,
        key_names: list[str],
        tags: EC2Tags,
        state_names: list[InstanceStateNameType] | None = None,
    ) -> list[EC2InstanceData]:
        # NOTE: be careful: Name=instance-state-name,Values=["pending", "running"] means pending OR running
        # NOTE2: AND is done by repeating Name=instance-state-name,Values=pending Name=instance-state-name,Values=running
        if state_names is None:
            state_names = ["pending", "running"]

        filters: list[FilterTypeDef] = [
            {
                "Name": "key-name",
                "Values": key_names,
            },
            {"Name": "instance-state-name", "Values": state_names},
        ]
        filters.extend(
            [{"Name": f"tag:{key}", "Values": [value]} for key, value in tags.items()]
        )

        instances = await self.client.describe_instances(Filters=filters)
        all_instances = []
        for reservation in instances["Reservations"]:
            assert "Instances" in reservation  # nosec
            for instance in reservation["Instances"]:
                assert "LaunchTime" in instance  # nosec
                assert "InstanceId" in instance  # nosec
                assert "PrivateDnsName" in instance  # nosec
                assert "InstanceType" in instance  # nosec
                assert "State" in instance  # nosec
                assert "Name" in instance["State"]  # nosec
                ec2_instance_types = await self.get_ec2_instance_capabilities(
                    {instance["InstanceType"]}
                )
                assert len(ec2_instance_types) == 1  # nosec
                assert "Tags" in instance  # nosec
                all_instances.append(
                    EC2InstanceData(
                        launch_time=instance["LaunchTime"],
                        id=instance["InstanceId"],
                        aws_private_dns=instance["PrivateDnsName"],
                        aws_public_ip=instance["PublicIpAddress"]
                        if "PublicIpAddress" in instance
                        else None,
                        type=instance["InstanceType"],
                        state=instance["State"]["Name"],
                        resources=Resources(
                            cpus=ec2_instance_types[0].cpus,
                            ram=ec2_instance_types[0].ram,
                        ),
                        tags=parse_obj_as(
                            EC2Tags,
                            {tag["Key"]: tag["Value"] for tag in instance["Tags"]},
                        ),
                    )
                )
        _logger.debug(
            "received: %s instances with %s", f"{len(all_instances)}", f"{state_names=}"
        )
        return all_instances

    async def terminate_instances(self, instance_datas: list[EC2InstanceData]) -> None:
        try:
            with log_context(
                _logger,
                logging.INFO,
                msg=f"terminating instances {[i.id for i in instance_datas]}",
            ):
                await self.client.terminate_instances(
                    InstanceIds=[i.id for i in instance_datas]
                )
        except botocore.exceptions.ClientError as exc:
            if (
                exc.response.get("Error", {}).get("Code", "")
                == "InvalidInstanceID.NotFound"
            ):
                raise EC2InstanceNotFoundError from exc
            raise  # pragma: no cover

    async def set_instances_tags(
        self, instances: list[EC2InstanceData], *, tags: EC2Tags
    ) -> None:
        try:
            with log_context(
                _logger,
                logging.DEBUG,
                msg=f"setting {tags=} on instances '[{[i.id for i in instances]}]'",
            ):
                await self.client.create_tags(
                    Resources=[i.id for i in instances],
                    Tags=[
                        {"Key": tag_key, "Value": tag_value}
                        for tag_key, tag_value in tags.items()
                    ],
                )
        except botocore.exceptions.ClientError as exc:
            if exc.response.get("Error", {}).get("Code", "") == "InvalidID":
                raise EC2InstanceNotFoundError from exc
            raise  # pragma: no cover
