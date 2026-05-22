"""Tracing utilities for per-instance lifecycle spans with span links.

Trace context is persisted as EC2 tags on the instance itself, ensuring it
survives service restarts and is accessible by any autoscaling service replica.
"""

import logging
from contextlib import contextmanager
from typing import Final

from aws_library.ec2 import AWSTagKey, AWSTagValue, EC2InstanceData, EC2Tags
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.trace import Link
from pydantic import TypeAdapter
from servicelib.tracing import (
    TracingConfig,
    extract_span_link_from_trace_carrier,
    get_trace_carrier_from_current_context,
    traced_operation,
)

_logger = logging.getLogger(__name__)

TRACEPARENT_EC2_TAG_KEY: Final[AWSTagKey] = TypeAdapter(AWSTagKey).validate_python("io.simcore.autoscaling.traceparent")


def get_tracing_config(app: FastAPI) -> TracingConfig:
    return app.state.tracing_config


def _get_instance_attributes(
    ec2_instance: EC2InstanceData,
    *,
    hostname: str | None = None,
) -> dict[str, str]:
    attributes: dict[str, str] = {
        "ec2.instance_id": ec2_instance.id,
        "ec2.instance_type": ec2_instance.type,
    }
    if hostname:
        attributes["docker.node.hostname"] = hostname
    return attributes


def get_trace_carrier_ec2_tags() -> EC2Tags:
    """Return EC2 tags containing the current trace context (traceparent).

    Should be called during instance launch within an active span so that
    the tag is set on the new EC2 instance.
    Returns an empty dict if no active trace context.
    """
    carrier = get_trace_carrier_from_current_context()
    if carrier and (traceparent := carrier.get("traceparent")):
        return {TRACEPARENT_EC2_TAG_KEY: TypeAdapter(AWSTagValue).validate_python(traceparent)}
    return {}


def _get_instance_span_link(ec2_instance: EC2InstanceData) -> Link | None:
    """Extract a span link from the traceparent stored in the instance's EC2 tags."""
    traceparent = ec2_instance.tags.get(TRACEPARENT_EC2_TAG_KEY)
    if not traceparent:
        return None
    carrier = {"traceparent": traceparent}
    return extract_span_link_from_trace_carrier(
        carrier=carrier,
        link_attributes={"link.type": "instance_launch", "ec2.instance_id": ec2_instance.id},
    )


@contextmanager
def traced_instance_lifecycle(
    operation_name: str,
    *,
    app: FastAPI,
    ec2_instance: EC2InstanceData,
    hostname: str | None = None,
    **extra_attributes: str,
):
    """Context manager for creating traced spans for EC2 instance lifecycle operations.

    Creates a span with instance-identifying attributes and optionally links
    back to the original launch span via the traceparent stored in EC2 tags.
    """
    tracing_config = get_tracing_config(app)

    attributes = _get_instance_attributes(ec2_instance, hostname=hostname)
    attributes.update(extra_attributes)

    # For root spans (no active parent), create a link back to the launch span
    current_span = trace.get_current_span()
    is_root_span = not current_span.is_recording()
    link = _get_instance_span_link(ec2_instance) if is_root_span else None

    with traced_operation(
        operation_name,
        tracing_config=tracing_config,
        attributes=attributes,
        links=[link] if link else None,
    ):
        yield
