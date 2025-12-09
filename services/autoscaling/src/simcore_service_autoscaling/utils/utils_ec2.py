"""Free helper functions for AWS API"""

import json
import logging
import re
from collections import OrderedDict
from collections.abc import Callable
from textwrap import dedent
from typing import Final

from aws_library.ec2 import AWSTagKey, AWSTagValue, EC2InstanceType, EC2Tags, Resources
from aws_library.ec2._models import EC2InstanceData
from common_library.json_serialization import json_dumps
from pydantic import TypeAdapter
from settings_library import CUSTOM_PLACEMENT_LABEL_KEYS

from .._meta import VERSION
from ..core.errors import (
    ConfigurationError,
    Ec2InvalidDnsNameError,
    TaskBestFittingInstanceNotFoundError,
)
from ..core.settings import ApplicationSettings

_logger = logging.getLogger(__name__)

_EC2_INTERNAL_DNS_RE: Final[re.Pattern] = re.compile(r"^(?P<host_name>ip-[^.]+)\..+$")
_SIMCORE_AUTOSCALING_VERSION_TAG_KEY: Final[AWSTagKey] = TypeAdapter(
    AWSTagKey
).validate_python("io.simcore.autoscaling.version")
_SIMCORE_AUTOSCALING_NODE_LABELS_TAG_KEY: Final[AWSTagKey] = TypeAdapter(
    AWSTagKey
).validate_python("io.simcore.autoscaling.monitored_nodes_labels")
_SIMCORE_AUTOSCALING_SERVICE_LABELS_TAG_KEY: Final[AWSTagKey] = TypeAdapter(
    AWSTagKey
).validate_python("io.simcore.autoscaling.monitored_services_labels")
_SIMCORE_AUTOSCALING_DASK_SCHEDULER_URL_TAG_KEY: Final[AWSTagKey] = TypeAdapter(
    AWSTagKey
).validate_python("io.simcore.autoscaling.dask-scheduler_url")
_SIMCORE_AUTOSCALING_CUSTOM_PLACEMENT_LABELS_TAG_KEY: Final[AWSTagKey] = TypeAdapter(
    AWSTagKey
).validate_python("io.simcore.autoscaling.ec2_instance.docker_node_labels")
_EC2_NAME_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python("Name")


def serialize_custom_placement_labels_to_ec2_tag(
    labels: dict[str, str],
) -> str:
    """Serialize custom placement labels to a JSON string for EC2 tag storage."""
    # Only include labels that are in the approved set
    filtered_labels = {
        k: v for k, v in labels.items() if k in CUSTOM_PLACEMENT_LABEL_KEYS
    }
    return json_dumps(filtered_labels) if filtered_labels else "{}"


def deserialize_custom_placement_labels_from_ec2_tag(
    tag_value: str | None,
) -> dict[str, str]:
    """Deserialize custom placement labels from EC2 tag value."""
    if not tag_value:
        return {}
    try:
        return json.loads(tag_value)
    except (json.JSONDecodeError, TypeError):
        _logger.warning(
            "Failed to deserialize custom placement labels from tag: %s", tag_value
        )
        return {}


def get_ec2_tags_dynamic(app_settings: ApplicationSettings) -> EC2Tags:
    assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    return {
        _SIMCORE_AUTOSCALING_VERSION_TAG_KEY: TypeAdapter(AWSTagValue).validate_python(
            f"{VERSION}"
        ),
        _SIMCORE_AUTOSCALING_NODE_LABELS_TAG_KEY: TypeAdapter(
            AWSTagValue
        ).validate_python(
            json_dumps(
                app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NODE_LABELS
            )
        ),
        _SIMCORE_AUTOSCALING_SERVICE_LABELS_TAG_KEY: TypeAdapter(
            AWSTagValue
        ).validate_python(
            json_dumps(
                app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_SERVICE_LABELS
            )
        ),
        # NOTE: this one gets special treatment in AWS GUI and is applied to the name of the instance
        _EC2_NAME_TAG_KEY: TypeAdapter(AWSTagValue).validate_python(
            f"{app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_NAME_PREFIX}-{app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_KEY_NAME}"
        ),
    } | app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_CUSTOM_TAGS


def get_ec2_tags_computational(app_settings: ApplicationSettings) -> EC2Tags:
    assert app_settings.AUTOSCALING_DASK  # nosec
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    return {
        _SIMCORE_AUTOSCALING_VERSION_TAG_KEY: TypeAdapter(AWSTagValue).validate_python(
            f"{VERSION}"
        ),
        _SIMCORE_AUTOSCALING_DASK_SCHEDULER_URL_TAG_KEY: TypeAdapter(
            AWSTagValue
        ).validate_python(f"{app_settings.AUTOSCALING_DASK.DASK_MONITORING_URL}"),
        # NOTE: this one gets special treatment in AWS GUI and is applied to the name of the instance
        _EC2_NAME_TAG_KEY: TypeAdapter(AWSTagValue).validate_python(
            f"{app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_NAME_PREFIX}-{app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_KEY_NAME}"
        ),
    } | app_settings.AUTOSCALING_EC2_INSTANCES.EC2_INSTANCES_CUSTOM_TAGS


def compose_user_data(docker_join_bash_command: str) -> str:
    return dedent(
        f"""\
#!/bin/bash
{docker_join_bash_command}
"""
    )


def closest_instance_policy(
    ec2_instance: EC2InstanceType,
    resources: Resources,
) -> float:
    """Scores how well an EC2 instance fits the requested resources.
    The higher the score the better the fit.
    """
    # if the instance does not satisfy the requested resources return 0
    if not (ec2_instance.resources >= resources):
        # NOTE: this is the construction such that if any of the
        # resources in resources is larger it will return True
        return 0

    if ec2_instance.resources == resources:
        return 100.0

    # compute a score for all the instances that are above expectations
    # best is the exact ec2 instance
    assert ec2_instance.resources.cpus > 0  # nosec
    assert ec2_instance.resources.ram > 0  # nosec
    max_cpu_usage_ratio = float(resources.cpus) / float(ec2_instance.resources.cpus)
    max_ram_usage_ratio = float(resources.ram) / float(ec2_instance.resources.ram)
    # for generic resources we could add more ratios here
    generic_usage_ratio = 1.0
    for resource_name, resource_value in resources.generic_resources.items():
        if isinstance(resource_value, str):
            # NOTE: for string resources we cannot compute a ratio
            continue
        # the resource exist on the instance otherwise > would have returned 0 above
        ec2_resource_value = ec2_instance.resources.generic_resources[resource_name]
        usage_ratio = float(resource_value) / float(ec2_resource_value)
        generic_usage_ratio *= usage_ratio

    return 100 * max_cpu_usage_ratio * max_ram_usage_ratio * generic_usage_ratio


def find_best_fitting_ec2_instance(
    allowed_ec2_instances: list[EC2InstanceType],
    resources: Resources,
    score_type: Callable[[EC2InstanceType, Resources], float] = closest_instance_policy,
) -> EC2InstanceType:
    if not allowed_ec2_instances:
        raise ConfigurationError(msg="allowed ec2 instances is missing!")
    score_to_ec2_candidate: dict[float, EC2InstanceType] = OrderedDict(
        sorted(
            {
                score_type(instance, resources): instance
                for instance in allowed_ec2_instances
            }.items(),
            reverse=True,
        )
    )

    score, instance = next(iter(score_to_ec2_candidate.items()))
    if score == 0:
        raise TaskBestFittingInstanceNotFoundError(needed_resources=resources)

    return instance


def node_host_name_from_ec2_private_dns(
    ec2_instance_data: EC2InstanceData,
) -> str:
    """returns the node host name 'ip-10-2-3-22' from the ec2 private dns
    Raises:
        Ec2InvalidDnsNameError: if the dns name does not follow the expected pattern
    """
    if match := re.match(_EC2_INTERNAL_DNS_RE, ec2_instance_data.aws_private_dns):
        host_name: str = match.group("host_name")
        return host_name
    raise Ec2InvalidDnsNameError(aws_private_dns_name=ec2_instance_data.aws_private_dns)


def node_ip_from_ec2_private_dns(
    ec2_instance_data: EC2InstanceData,
) -> str:
    """returns the node ipv4 from the ec2 private dns string
    Raises:
        Ec2InvalidDnsNameError: if the dns name does not follow the expected pattern
    """
    return (
        node_host_name_from_ec2_private_dns(ec2_instance_data)
        .removeprefix("ip-")
        .replace("-", ".")
    )
