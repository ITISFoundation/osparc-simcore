"""Free helper functions for AWS API"""

import logging
import re
from collections import OrderedDict
from collections.abc import Callable
from operator import itemgetter
from textwrap import dedent
from typing import Final

from aws_library.ec2 import (
    AWS_TAG_VALUE_MAX_LENGTH,
    AWSTagKey,
    AWSTagValue,
    EC2InstanceType,
    EC2Tags,
    Resources,
)
from aws_library.ec2._models import EC2InstanceData
from common_library.json_serialization import json_dumps
from models_library.docker import (
    OSPARC_CUSTOM_DOCKER_PLACEMENT_CONSTRAINTS_LABEL_KEYS,
    DockerLabelKey,
)
from pydantic import TypeAdapter

from .._meta import VERSION
from ..core.errors import (
    ConfigurationError,
    Ec2InvalidDnsNameError,
    Ec2TagDeserializationError,
    TaskBestFittingInstanceNotFoundError,
)
from ..core.settings import ApplicationSettings

_logger = logging.getLogger(__name__)

_EC2_INTERNAL_DNS_RE: Final[re.Pattern] = re.compile(r"^(?P<host_name>ip-[^.]+)\..+$")
_SIMCORE_AUTOSCALING_VERSION_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python(
    "io.simcore.autoscaling.version"
)
_SIMCORE_AUTOSCALING_NODE_LABELS_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python(
    "io.simcore.autoscaling.monitored_nodes_labels"
)
_SIMCORE_AUTOSCALING_SERVICE_LABELS_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python(
    "io.simcore.autoscaling.monitored_services_labels"
)
_SIMCORE_AUTOSCALING_DASK_SCHEDULER_URL_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python(
    "io.simcore.autoscaling.dask-scheduler_url"
)
_SIMCORE_AUTOSCALING_CUSTOM_PLACEMENT_LABELS_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python(
    "io.simcore.autoscaling.ec2_instance.docker_node_labels"
)
_EC2_NAME_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python("Name")


def _create_chunked_tag_pattern(base_key: AWSTagKey) -> re.Pattern:
    """Create a regex pattern for matching both single and chunked EC2 tags.

    Args:
        base_key: The base tag key to match (e.g., "io.simcore.autoscaling.pre_pulled_images")

    Returns:
        A compiled regex pattern that matches:
        - Single tag format: base_key
        - Chunked tag format: base_key_0, base_key_1, base_key_2, etc.

    Examples:
        >>> pattern = create_chunked_tag_pattern("my.tag")
        >>> pattern.match("my.tag")  # Matches single tag
        >>> pattern.match("my.tag_0")  # Matches first chunk
        >>> pattern.match("my.tag_123")  # Matches chunk 123
    """
    return re.compile(rf"^{re.escape(base_key)}(_\d+)?$")


def dump_as_ec2_tags[T](data: T, *, base_tag_key: AWSTagKey) -> EC2Tags:  # pyright: ignore[reportInvalidTypeVarUse]
    """Serialize data to EC2 tags, chunking only if necessary to fit AWS tag size limits.

    AWS Tag Values are limited to 256 characters. This function serializes the data
    to JSON and stores it in either:
    - A single tag (base_tag_key) if the JSON is <= 256 chars
    - Multiple chunked tags (base_tag_key_0, base_tag_key_1, ...) if > 256 chars

    Args:
        data: Any JSON-serializable data (list, dict, etc.)
        base_tag_key: The base key for the EC2 tag(s)

    Returns:
        EC2Tags dict with either a single tag or multiple chunked tags

    Examples:
        >>> # Small data fits in single tag
        >>> dump_as_ec2_tags(["image:v1"], "images")
        {"images": '["image:v1"]'}

        >>> # Large data gets chunked
        >>> dump_as_ec2_tags(large_list, "images")
        {"images_0": "...", "images_1": "...", "images_2": "..."}
    """
    jsonized_data = json_dumps(data)
    assert AWS_TAG_VALUE_MAX_LENGTH  # nosec

    # If data fits in single tag, use simple format
    if len(jsonized_data) <= AWS_TAG_VALUE_MAX_LENGTH:
        return {base_tag_key: TypeAdapter(AWSTagValue).validate_python(jsonized_data)}

    # Data exceeds limit, chunk it
    chunks = [
        jsonized_data[i : i + AWS_TAG_VALUE_MAX_LENGTH] for i in range(0, len(jsonized_data), AWS_TAG_VALUE_MAX_LENGTH)
    ]

    return {
        TypeAdapter(AWSTagKey).validate_python(f"{base_tag_key}_{i}"): TypeAdapter(AWSTagValue).validate_python(chunk)
        for i, chunk in enumerate(chunks)
    }


def load_from_ec2_tags[T](tags: EC2Tags, *, base_tag_key: AWSTagKey, type_adapter: TypeAdapter[T]) -> T | None:
    """Load and deserialize data from EC2 tags, handling both single and chunked formats.

    When data is JSON-serialized:
    - If <= AWS_TAG_VALUE_MAX_LENGTH (e.g. 256) chars: stored in a single tag with key base_tag_key
    - If > AWS_TAG_VALUE_MAX_LENGTH chars: stored in chunked tags (base_tag_key_0, base_tag_key_1, ...)

    Args:
        tags: EC2Tags dict to load from
        base_tag_key: The base key used when dumping the data
        type_adapter: TypeAdapter for validating and typing the deserialized data

    Returns:
        The deserialized and validated data of type T, or None if no tags found

    Raises:
        Ec2TagDeserializationError: If JSON is malformed or deserialization fails

    Examples:
        >>> # Single tag format (small data)
        >>> tags = {"images": '["image:v1"]'}
        >>> load_from_ec2_tags(tags, "images", TypeAdapter(list[str]))
        ["image:v1"]

        >>> # Chunked format (large data)
        >>> tags = {"images_0": "...", "images_1": "...", "images_2": "..."}
        >>> load_from_ec2_tags(tags, "images", TypeAdapter(list[str]))
        [...]
    """
    # Check for single tag format first (used when data is small enough for single tag)
    if base_tag_key in tags:
        try:
            return type_adapter.validate_json(tags[base_tag_key])
        except ValueError as exc:
            raise Ec2TagDeserializationError(tag_key=base_tag_key) from exc

    # Check for chunked format (base_tag_key_0, base_tag_key_1, ...)
    # Note: if we have chunked tags, base_tag_key itself will NOT be in tags
    pattern = _create_chunked_tag_pattern(base_tag_key)
    matching_tags = [
        (int(match.group(1).lstrip("_")), value)
        for key, value in tags.items()
        if (match := pattern.match(key)) and match.group(1) is not None
    ]

    if not matching_tags:
        # No tags found
        return None

    # Assemble chunks in order
    try:
        assembled_json = "".join(map(itemgetter(1), sorted(matching_tags, key=itemgetter(0))))
        return type_adapter.validate_json(assembled_json)
    except ValueError as exc:
        raise Ec2TagDeserializationError(tag_key=base_tag_key) from exc


def list_tag_keys(tags: EC2Tags, *, base_tag_key: AWSTagKey) -> list[AWSTagKey]:
    """List all EC2 tag keys that match the base key (single or chunked format).

    This function identifies both:
    - Single tag format: base_tag_key
    - Chunked format: base_tag_key_0, base_tag_key_1, base_tag_key_2, ...

    Args:
        tags: EC2Tags dict to search
        base_tag_key: The base key to match

    Returns:
        List of matching tag keys

    Examples:
        >>> tags = {"images_0": "...", "images_1": "...", "other": "..."}
        >>> list_chunked_tag_keys(tags, "images")
        ["images_0", "images_1"]

        >>> tags = {"images": "...", "other": "..."}
        >>> list_chunked_tag_keys(tags, "images")
        ["images"]
    """
    pattern = _create_chunked_tag_pattern(base_tag_key)
    return [TypeAdapter(AWSTagKey).validate_python(key) for key in tags if pattern.match(key)]


def dump_task_required_node_labels_as_tags(
    labels: dict[DockerLabelKey, str],
) -> EC2Tags:
    """Serialize custom placement labels to EC2 tags with chunking support.

    Only includes labels from the approved set (OSPARC_CUSTOM_DOCKER_PLACEMENT_CONSTRAINTS_LABEL_KEYS).
    Uses chunking if the serialized data exceeds AWS tag size limits.

    Args:
        labels: Dict of placement constraint labels to serialize

    Returns:
        EC2Tags dict with either single or chunked tags
    """
    # Only include labels that are in the approved set
    filtered_labels = {k: v for k, v in labels.items() if k in OSPARC_CUSTOM_DOCKER_PLACEMENT_CONSTRAINTS_LABEL_KEYS}
    return dump_as_ec2_tags(
        filtered_labels,
        base_tag_key=_SIMCORE_AUTOSCALING_CUSTOM_PLACEMENT_LABELS_TAG_KEY,
    )


def load_task_required_docker_node_labels_from_tags(
    tags: EC2Tags,
) -> dict[DockerLabelKey, str]:
    """Deserialize custom placement labels from EC2 tags.

    Handles both single tag and chunked tag formats. Returns empty dict
    if no placement labels are found.

    Args:
        tags: EC2Tags dict to load from

    Returns:
        Dict of placement constraint labels (empty dict if no tags found)

    Raises:
        Ec2TagDeserializationError: If tag data is malformed
    """
    result = load_from_ec2_tags(
        tags,
        base_tag_key=_SIMCORE_AUTOSCALING_CUSTOM_PLACEMENT_LABELS_TAG_KEY,
        type_adapter=TypeAdapter(dict[DockerLabelKey, str]),
    )
    return result if result is not None else {}


def list_task_required_node_labels_tag_keys(tags: EC2Tags) -> list[AWSTagKey]:
    """List all custom placement label tag keys from EC2 tags.

    Identifies both single and chunked tag formats for custom placement labels.

    Args:
        tags: EC2Tags dict to search

    Returns:
        List of matching tag keys (empty list if none found)
    """
    return list_tag_keys(tags, base_tag_key=_SIMCORE_AUTOSCALING_CUSTOM_PLACEMENT_LABELS_TAG_KEY)


def get_ec2_tags_dynamic(app_settings: ApplicationSettings) -> EC2Tags:
    assert app_settings.AUTOSCALING_NODES_MONITORING  # nosec
    assert app_settings.AUTOSCALING_EC2_INSTANCES  # nosec
    return {
        _SIMCORE_AUTOSCALING_VERSION_TAG_KEY: TypeAdapter(AWSTagValue).validate_python(f"{VERSION}"),
        _SIMCORE_AUTOSCALING_NODE_LABELS_TAG_KEY: TypeAdapter(AWSTagValue).validate_python(
            json_dumps(app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_NODE_LABELS)
        ),
        _SIMCORE_AUTOSCALING_SERVICE_LABELS_TAG_KEY: TypeAdapter(AWSTagValue).validate_python(
            json_dumps(app_settings.AUTOSCALING_NODES_MONITORING.NODES_MONITORING_SERVICE_LABELS)
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
        _SIMCORE_AUTOSCALING_VERSION_TAG_KEY: TypeAdapter(AWSTagValue).validate_python(f"{VERSION}"),
        _SIMCORE_AUTOSCALING_DASK_SCHEDULER_URL_TAG_KEY: TypeAdapter(AWSTagValue).validate_python(
            f"{app_settings.AUTOSCALING_DASK.DASK_MONITORING_URL}"
        ),
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
            {score_type(instance, resources): instance for instance in allowed_ec2_instances}.items(),
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
    return node_host_name_from_ec2_private_dns(ec2_instance_data).removeprefix("ip-").replace("-", ".")
