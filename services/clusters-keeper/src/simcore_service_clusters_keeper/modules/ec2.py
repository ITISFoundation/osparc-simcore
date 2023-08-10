import contextlib
import logging
from dataclasses import dataclass
from typing import cast

import aioboto3
import botocore.exceptions
from aiobotocore.session import ClientCreatorContext
from fastapi import FastAPI
from pydantic import ByteSize, parse_obj_as
from servicelib.logging_utils import log_context
from tenacity._asyncio import AsyncRetrying
from tenacity.before_sleep import before_sleep_log
from tenacity.stop import stop_after_delay
from tenacity.wait import wait_random_exponential
from types_aiobotocore_ec2 import EC2Client
from types_aiobotocore_ec2.literals import InstanceStateNameType, InstanceTypeType
from types_aiobotocore_ec2.type_defs import FilterTypeDef

from ..core.errors import (
    ConfigurationError,
    Ec2InstanceNotFoundError,
    Ec2NotConnectedError,
    Ec2TooManyInstancesError,
)
from ..core.settings import EC2InstancesSettings, EC2Settings, get_application_settings
from ..models import EC2InstanceData, EC2InstanceType
from ..utils.ec2 import compose_user_data

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ClustersKeeperEC2:
    client: EC2Client
    session: aioboto3.Session
    exit_stack: contextlib.AsyncExitStack

    @classmethod
    async def create(cls, settings: EC2Settings) -> "ClustersKeeperEC2":
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

    async def get_ec2_instance_capabilities(
        self,
        instance_type_names: set[InstanceTypeType],
    ) -> list[EC2InstanceType]:
        """instance_type_names must be a set of unique values"""
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
                        ram=parse_obj_as(
                            ByteSize, f"{instance['MemoryInfo']['SizeInMiB']}MiB"
                        ),
                    )
                )
        return list_instances

    async def start_aws_instance(
        self,
        instance_settings: EC2InstancesSettings,
        instance_type: InstanceTypeType,
        tags: dict[str, str],
        startup_script: str,
        number_of_instances: int,
    ) -> list[EC2InstanceData]:
        with log_context(
            logger,
            logging.INFO,
            msg=f"launching {number_of_instances} AWS instance(s) {instance_type} with {tags=}",
        ):
            # first check the max amount is not already reached
            current_instances = await self.get_instances(instance_settings, tags)
            if (
                len(current_instances) + number_of_instances
                > instance_settings.EC2_INSTANCES_MAX_INSTANCES
            ):
                raise Ec2TooManyInstancesError(
                    num_instances=instance_settings.EC2_INSTANCES_MAX_INSTANCES
                )

            instances = await self.client.run_instances(
                ImageId=instance_settings.EC2_INSTANCES_AMI_ID,
                MinCount=number_of_instances,
                MaxCount=number_of_instances,
                InstanceType=instance_type,
                InstanceInitiatedShutdownBehavior="terminate",
                KeyName=instance_settings.EC2_INSTANCES_KEY_NAME,
                TagSpecifications=[
                    {
                        "ResourceType": "instance",
                        "Tags": [
                            {"Key": tag_key, "Value": tag_value}
                            for tag_key, tag_value in tags.items()
                        ],
                    }
                ],
                UserData=compose_user_data(startup_script),
                NetworkInterfaces=[
                    {
                        "AssociatePublicIpAddress": True,
                        "DeviceIndex": 0,
                        "SubnetId": instance_settings.EC2_INSTANCES_SUBNET_ID,
                        "Groups": instance_settings.EC2_INSTANCES_SECURITY_GROUP_IDS,
                    }
                ],
            )
            instance_ids = [i["InstanceId"] for i in instances["Instances"]]
            logger.info(
                "New instances launched: %s, waiting for them to start now...",
                instance_ids,
            )

            # wait for the instance to be in a pending state
            # NOTE: reference to EC2 states https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-instance-lifecycle.html
            waiter = self.client.get_waiter("instance_exists")
            await waiter.wait(InstanceIds=instance_ids)
            logger.info("instances %s exists now.", instance_ids)

            # get the private IPs
            instances = await self.client.describe_instances(InstanceIds=instance_ids)
            instance_datas = [
                EC2InstanceData(
                    launch_time=instance["LaunchTime"],
                    id=instance["InstanceId"],
                    aws_private_dns=instance["PrivateDnsName"],
                    type=instance["InstanceType"],
                    state=instance["State"]["Name"],
                )
                for instance in instances["Reservations"][0]["Instances"]
            ]
            logger.info(
                "%s is available, happy computing!!",
                f"{instance_datas=}",
            )
            return instance_datas

    async def get_instances(
        self,
        instance_settings: EC2InstancesSettings,
        tags: dict[str, str],
        *,
        state_names: list[InstanceStateNameType] | None = None,
    ) -> list[EC2InstanceData]:
        # NOTE: be careful: Name=instance-state-name,Values=["pending", "running"] means pending OR running
        # NOTE2: AND is done by repeating Name=instance-state-name,Values=pending Name=instance-state-name,Values=running
        if state_names is None:
            state_names = ["pending", "running"]

        filters: list[FilterTypeDef] = [
            {
                "Name": "key-name",
                "Values": [instance_settings.EC2_INSTANCES_KEY_NAME],
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
                all_instances.append(
                    EC2InstanceData(
                        launch_time=instance["LaunchTime"],
                        id=instance["InstanceId"],
                        aws_private_dns=instance["PrivateDnsName"],
                        type=instance["InstanceType"],
                        state=instance["State"]["Name"],
                    )
                )
        logger.debug(
            "received: %s instances with %s", f"{len(all_instances)}", f"{state_names=}"
        )
        return all_instances

    async def terminate_instances(self, instance_datas: list[EC2InstanceData]) -> None:
        try:
            await self.client.terminate_instances(
                InstanceIds=[i.id for i in instance_datas]
            )
        except botocore.exceptions.ClientError as exc:
            if (
                exc.response.get("Error", {}).get("Code", "")
                == "InvalidInstanceID.NotFound"
            ):
                raise Ec2InstanceNotFoundError from exc
            raise

    async def set_instances_tags(
        self, instances: list[EC2InstanceData], tags: dict[str, str]
    ) -> None:
        with log_context(
            logger,
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


def setup(app: FastAPI) -> None:
    async def on_startup() -> None:
        app.state.ec2_client = None

        settings: EC2Settings | None = get_application_settings(
            app
        ).CLUSTERS_KEEPER_EC2_ACCESS

        if not settings:
            logger.warning("EC2 client is de-activated in the settings")
            return

        app.state.ec2_client = client = await ClustersKeeperEC2.create(settings)

        async for attempt in AsyncRetrying(
            reraise=True,
            stop=stop_after_delay(120),
            wait=wait_random_exponential(max=30),
            before_sleep=before_sleep_log(logger, logging.WARNING),
        ):
            with attempt:
                connected = await client.ping()
                if not connected:
                    raise Ec2NotConnectedError

    async def on_shutdown() -> None:
        if app.state.ec2_client:
            await cast(ClustersKeeperEC2, app.state.ec2_client).close()

    app.add_event_handler("startup", on_startup)
    app.add_event_handler("shutdown", on_shutdown)


def get_ec2_client(app: FastAPI) -> ClustersKeeperEC2:
    if not app.state.ec2_client:
        raise ConfigurationError(
            msg="EC2 client is not available. Please check the configuration."
        )
    return cast(ClustersKeeperEC2, app.state.ec2_client)
