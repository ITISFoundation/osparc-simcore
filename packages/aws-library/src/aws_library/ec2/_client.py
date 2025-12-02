import contextlib
import logging
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Literal, cast

import aioboto3
import botocore.exceptions
from aiobotocore.session import ClientCreatorContext
from aiocache import cached  # type: ignore[import-untyped]
from pydantic import ByteSize, PositiveInt
from servicelib.logging_utils import log_context
from settings_library.ec2 import EC2Settings
from types_aiobotocore_ec2 import EC2Client
from types_aiobotocore_ec2.literals import InstanceStateNameType, InstanceTypeType
from types_aiobotocore_ec2.type_defs import (
    FilterTypeDef,
    TagTypeDef,
)

from ._error_handler import ec2_exception_handler
from ._errors import (
    EC2InstanceNotFoundError,
    EC2InsufficientCapacityError,
    EC2SubnetsNotEnoughIPsError,
)
from ._models import (
    AWSTagKey,
    EC2InstanceConfig,
    EC2InstanceData,
    EC2InstanceType,
    EC2Tags,
    Resources,
)
from ._utils import (
    check_max_number_of_instances_not_exceeded,
    compose_user_data,
    ec2_instance_data_from_aws_instance,
    get_subnet_azs,
    get_subnet_capacity,
)

_logger = logging.getLogger(__name__)


@dataclass()
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
        with contextlib.suppress(Exception):
            await self.client.describe_account_attributes()
            return True
        return False

    @cached(noself=True)
    @ec2_exception_handler(_logger)
    async def get_ec2_instance_capabilities(
        self,
        instance_type_names: set[InstanceTypeType] | Literal["ALL"],
    ) -> list[EC2InstanceType]:
        """Returns the ec2 instance types from a list of instance type names (sorted by name)

        Arguments:
            instance_type_names -- the types to filter with or "ALL", to return all EC2 possible instances

        Raises:
            Ec2InstanceTypeInvalidError: some invalid types were used as filter
            ClustersKeeperRuntimeError: unexpected error communicating with EC2

        """
        if instance_type_names == "ALL":
            selection_or_all_if_empty = []
        else:
            selection_or_all_if_empty = list(instance_type_names)
            if len(selection_or_all_if_empty) == 0:
                msg = "`instance_type_names` cannot be an empty set. Use either a selection or 'ALL'"
                raise ValueError(msg)

        instance_types = await self.client.describe_instance_types(
            InstanceTypes=selection_or_all_if_empty
        )
        list_instances: list[EC2InstanceType] = []
        for instance in instance_types.get("InstanceTypes", []):
            with contextlib.suppress(KeyError):
                assert "InstanceType" in instance  # nosec
                assert "VCpuInfo" in instance  # nosec
                assert "DefaultVCpus" in instance["VCpuInfo"]  # nosec
                assert "MemoryInfo" in instance  # nosec
                assert "SizeInMiB" in instance["MemoryInfo"]  # nosec

                # Extract GPU information if available
                generic_resources: dict[str, int | float | str] = {}
                if "GpuInfo" in instance:
                    gpu_info = instance["GpuInfo"]
                    assert "Gpus" in gpu_info  # nosec
                    # Sum up all GPUs (some instances have multiple GPU types)
                    total_gpus = sum(gpu.get("Count", 0) for gpu in gpu_info["Gpus"])
                    total_vram_mib = sum(
                        gpu.get("Count", 0)
                        * gpu.get("MemoryInfo", {}).get("SizeInMiB", 0)
                        for gpu in gpu_info["Gpus"]
                    )

                    if total_gpus > 0:
                        generic_resources["GPU"] = total_gpus
                    if total_vram_mib > 0:
                        # Convert MiB to bytes for consistency with RAM
                        generic_resources["VRAM"] = total_vram_mib * 1024 * 1024

                list_instances.append(
                    EC2InstanceType(
                        name=instance["InstanceType"],
                        resources=Resources(
                            cpus=instance["VCpuInfo"]["DefaultVCpus"],
                            ram=ByteSize(
                                int(instance["MemoryInfo"]["SizeInMiB"]) * 1024 * 1024
                            ),
                            generic_resources=generic_resources,
                        ),
                    )
                )
        return sorted(list_instances, key=lambda i: i.name)

    @ec2_exception_handler(_logger)
    async def launch_instances(
        self,
        instance_config: EC2InstanceConfig,
        *,
        min_number_of_instances: PositiveInt,
        number_of_instances: PositiveInt,
        max_total_number_of_instances: PositiveInt = 10,
    ) -> list[EC2InstanceData]:
        """launch new EC2 instance(s)

        Arguments:
            instance_config -- The EC2 instance configuration
            min_number_of_instances -- the minimal number of instances required (fails if this amount cannot be reached)
            number_of_instances -- the ideal number of instances needed (it it cannot be reached AWS will return a number >=min_number_of_instances)
            max_total_number_of_instances -- The total maximum allowed number of instances for this given instance_config

        Raises:
            EC2TooManyInstancesError: max_total_number_of_instances would be exceeded
            EC2SubnetsNotEnoughIPsError: not enough IPs in the subnets
            EC2InsufficientCapacityError: not enough capacity in the subnets


        Returns:
            The created instance data infos
        """

        with log_context(
            _logger,
            logging.INFO,
            msg=f"launch {number_of_instances} AWS instance(s) {instance_config.type.name}"
            f" with {instance_config.tags=} in {instance_config.subnet_ids=}",
        ):
            # first check the max amount is not already reached
            await check_max_number_of_instances_not_exceeded(
                self,
                instance_config,
                required_number_instances=number_of_instances,
                max_total_number_of_instances=max_total_number_of_instances,
            )

            # NOTE: checking subnets capacity is not strictly needed as AWS will do it for us
            # but it gives us a chance to give early feedback to the user
            # and avoid trying to launch instances in subnets that are already full
            # and also allows to circumvent a moto bug that does not raise
            # InsufficientInstanceCapacity when a subnet is full
            subnet_id_to_available_ips = await get_subnet_capacity(
                self.client, subnet_ids=instance_config.subnet_ids
            )

            total_available_ips = sum(subnet_id_to_available_ips.values())
            if total_available_ips < min_number_of_instances:
                raise EC2SubnetsNotEnoughIPsError(
                    subnet_ids=instance_config.subnet_ids,
                    instance_type=instance_config.type.name,
                    available_ips=total_available_ips,
                )

            # now let's not try to run instances in subnets that have not enough IPs
            subnet_ids_with_capacity = [
                subnet_id
                for subnet_id, capacity in subnet_id_to_available_ips.items()
                if capacity >= min_number_of_instances
            ]

            resource_tags: list[TagTypeDef] = [
                {"Key": tag_key, "Value": tag_value}
                for tag_key, tag_value in instance_config.tags.items()
            ]

            # Try each subnet in order until one succeeds
            for subnet_id in subnet_ids_with_capacity:
                try:
                    _logger.debug(
                        "Attempting to launch instances in subnet %s", subnet_id
                    )

                    instances = await self.client.run_instances(
                        ImageId=instance_config.ami_id,
                        MinCount=min_number_of_instances,
                        MaxCount=number_of_instances,
                        IamInstanceProfile=(
                            {"Arn": instance_config.iam_instance_profile}
                            if instance_config.iam_instance_profile
                            else {}
                        ),
                        InstanceType=instance_config.type.name,
                        InstanceInitiatedShutdownBehavior="terminate",
                        KeyName=instance_config.key_name,
                        TagSpecifications=[
                            {"ResourceType": "instance", "Tags": resource_tags},
                            {"ResourceType": "volume", "Tags": resource_tags},
                            {
                                "ResourceType": "network-interface",
                                "Tags": resource_tags,
                            },
                        ],
                        UserData=compose_user_data(instance_config.startup_script),
                        NetworkInterfaces=[
                            {
                                "AssociatePublicIpAddress": True,
                                "DeviceIndex": 0,
                                "SubnetId": subnet_id,
                                "Groups": instance_config.security_group_ids,
                            }
                        ],
                    )
                    # If we get here, the launch succeeded
                    break
                except botocore.exceptions.ClientError as exc:
                    error_code = exc.response.get("Error", {}).get("Code")
                    if error_code == "InsufficientInstanceCapacity":
                        _logger.warning(
                            "Insufficient capacity in subnet %s for instance type %s, trying next subnet",
                            subnet_id,
                            instance_config.type.name,
                        )
                        continue
                    # For any other ClientError, re-raise to let the decorator handle it
                    raise

            else:
                subnet_zones = await get_subnet_azs(
                    self.client, subnet_ids=subnet_ids_with_capacity
                )
                raise EC2InsufficientCapacityError(
                    availability_zones=subnet_zones,
                    instance_type=instance_config.type.name,
                )
            instance_ids = [
                i["InstanceId"]  # pyright: ignore[reportTypedDictNotRequiredAccess]
                for i in instances["Instances"]
            ]
            with log_context(
                _logger,
                logging.INFO,
                msg=f"{len(instance_ids)} instances: {instance_ids=} launched. Wait to reach pending state",
            ):
                # wait for the instance to be in a pending state
                # NOTE: reference to EC2 states https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html
                waiter = self.client.get_waiter("instance_exists")
                await waiter.wait(InstanceIds=instance_ids)

            # NOTE: waiting for pending ensures we get all the IPs back
            described_instances = await self.client.describe_instances(
                InstanceIds=instance_ids
            )
            assert "Instances" in described_instances["Reservations"][0]  # nosec
            return [
                await ec2_instance_data_from_aws_instance(self, i)
                for i in described_instances["Reservations"][0]["Instances"]
            ]

    @ec2_exception_handler(_logger)
    async def get_instances(
        self,
        *,
        key_names: list[str],
        tags: EC2Tags,
        state_names: list[InstanceStateNameType] | None = None,
    ) -> list[EC2InstanceData]:
        """returns the instances matching the given criteria

        Arguments:
            key_names -- filter the instances by key names
            tags -- filter instances by key and their values

        Keyword Arguments:
            state_names -- filters the instances by state (pending, running, etc...) (default: {None})

        Returns:
            the instances found
        """
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
            all_instances.extend(
                [
                    await ec2_instance_data_from_aws_instance(self, i)
                    for i in reservation["Instances"]
                ]
            )
        _logger.debug(
            "received: %s instances with %s", f"{len(all_instances)}", f"{state_names=}"
        )
        return all_instances

    @ec2_exception_handler(_logger)
    async def start_instances(
        self, instance_datas: Iterable[EC2InstanceData]
    ) -> list[EC2InstanceData]:
        """starts stopped instances. Will return once the started instances are pending so that their IPs are available.

        Arguments:
            instance_datas -- the instances to start

        Raises:
            EC2InstanceNotFoundError: if some of the instance_datas are not found

        Returns:
            the started instance datas with their respective IPs
        """
        instance_ids = [i.id for i in instance_datas]
        with log_context(
            _logger,
            logging.INFO,
            msg=f"start instances {instance_ids}",
        ):
            await self.client.start_instances(InstanceIds=instance_ids)
            # wait for the instance to be in a pending state
            # NOTE: reference to EC2 states https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html
            waiter = self.client.get_waiter("instance_exists")
            await waiter.wait(InstanceIds=instance_ids)
            _logger.info("instances %s exists now.", instance_ids)
            # NOTE: waiting for pending ensure we get all the IPs back
            aws_instances = await self.client.describe_instances(
                InstanceIds=instance_ids
            )
            assert len(aws_instances["Reservations"]) == 1  # nosec
            assert "Instances" in aws_instances["Reservations"][0]  # nosec
            return [
                await ec2_instance_data_from_aws_instance(self, i)
                for i in aws_instances["Reservations"][0]["Instances"]
            ]

    @ec2_exception_handler(_logger)
    async def stop_instances(self, instance_datas: Iterable[EC2InstanceData]) -> None:
        """Stops running instances.
        Stopping an already stopped instance will do nothing.

        Arguments:
            instance_datas -- the instances to stop

        Raises:
            EC2InstanceNotFoundError: any of the instance_datas are not found
        """
        with log_context(
            _logger,
            logging.INFO,
            msg=f"stop instances {[i.id for i in instance_datas]}",
        ):
            await self.client.stop_instances(InstanceIds=[i.id for i in instance_datas])

    @ec2_exception_handler(_logger)
    async def terminate_instances(
        self, instance_datas: Iterable[EC2InstanceData]
    ) -> None:
        with log_context(
            _logger,
            logging.INFO,
            msg=f"terminate instances {[i.id for i in instance_datas]}",
        ):
            await self.client.terminate_instances(
                InstanceIds=[i.id for i in instance_datas]
            )

    @ec2_exception_handler(_logger)
    async def set_instances_tags(
        self, instances: Sequence[EC2InstanceData], *, tags: EC2Tags
    ) -> None:
        try:
            with log_context(
                _logger,
                logging.DEBUG,
                msg=f"set {tags=} on instances '[{[i.id for i in instances]}]'",
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

    @ec2_exception_handler(_logger)
    async def remove_instances_tags(
        self, instances: Sequence[EC2InstanceData], *, tag_keys: Iterable[AWSTagKey]
    ) -> None:
        try:
            with log_context(
                _logger,
                logging.DEBUG,
                msg=f"removal of {tag_keys=} from instances '[{[i.id for i in instances]}]'",
            ):
                await self.client.delete_tags(
                    Resources=[i.id for i in instances],
                    Tags=[{"Key": tag_key} for tag_key in tag_keys],
                )
        except botocore.exceptions.ClientError as exc:
            if exc.response.get("Error", {}).get("Code", "") == "InvalidID":
                raise EC2InstanceNotFoundError from exc
            raise  # pragma: no cover
