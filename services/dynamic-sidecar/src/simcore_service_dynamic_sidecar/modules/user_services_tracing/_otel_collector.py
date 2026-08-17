from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Final

import yaml
from servicelib.tracing import SourceOrigin, create_standard_attributes

from ._settings import UserServicesTracingSettings

if TYPE_CHECKING:
    from ...core.settings import ApplicationSettings

OTEL_COLLECTOR_SERVICE_NAME: Final[str] = "dy-otel-http-collector"


def build_otel_collector_config(
    user_services_tracing_settings: UserServicesTracingSettings,
    settings: ApplicationSettings,
) -> str:
    attributes = create_standard_attributes(
        user_id=settings.DY_SIDECAR_USER_ID,
        project_id=settings.DY_SIDECAR_PROJECT_ID,
        node_id=settings.DY_SIDECAR_NODE_ID,
        product_name=settings.DY_SIDECAR_PRODUCT_NAME,
        run_id=settings.DY_SIDECAR_RUN_ID,
        source_origin=SourceOrigin.USER_SERVICE,
    )

    config = {
        "receivers": {
            "otlp": {
                "protocols": {
                    "http": {"endpoint": "0.0.0.0:4318"},
                }
            }
        },
        "processors": {
            "batch": {"timeout": "5s"},
            "resource": {"attributes": [{"key": k, "value": v, "action": "upsert"} for k, v in attributes.items()]},
        },
        "exporters": {
            "file": {
                "path": "/traces/spans.jsonl",
                "rotation": {
                    "max_megabytes": user_services_tracing_settings.USER_SERVICES_TRACING_COLLECTOR_MAX_FILE_SIZE_MB,
                    "max_backups": user_services_tracing_settings.USER_SERVICES_TRACING_COLLECTOR_MAX_BACKUPS,
                },
                "flush_interval": (
                    f"{int(user_services_tracing_settings.USER_SERVICES_TRACING_COLLECTOR_FLUSH_INTERVAL.total_seconds())}s"
                ),
            }
        },
        "service": {
            "pipelines": {
                "traces": {
                    "receivers": ["otlp"],
                    "processors": ["batch", "resource"],
                    "exporters": ["file"],
                }
            }
        },
    }
    return yaml.safe_dump(config, default_flow_style=False)


def build_otel_resource_attributes(settings: ApplicationSettings) -> str:
    attrs = create_standard_attributes(
        service_key=settings.DY_SIDECAR_SERVICE_KEY,
        service_version=settings.DY_SIDECAR_SERVICE_VERSION,
        source_origin=None,
    )
    return ",".join(f"{k}={v}" for k, v in attrs.items() if v)


def build_otel_collector_compose_service(
    user_services_tracing_settings: UserServicesTracingSettings,
    settings: ApplicationSettings,
    collector_container_name: str,
    traces_volume_mount: str,
) -> dict[str, Any]:
    assert settings.DYNAMIC_SIDECAR_TRACING  # nosec
    collector_config_yaml = build_otel_collector_config(user_services_tracing_settings, settings)
    collector_image = (
        f"{user_services_tracing_settings.USER_SERVICES_TRACING_COLLECTOR_IMAGE_NAME}:"
        f"{settings.DYNAMIC_SIDECAR_TRACING.TRACING_OPENTELEMETRY_COLLECTOR_IMAGE_VERSION}"
    )
    return {
        "image": collector_image,
        "container_name": collector_container_name,
        "user": f"{os.getuid()}:{os.getgid()}",
        "command": ["--config=env:OTEL_COLLECTOR_CONFIG"],
        "environment": [f"OTEL_COLLECTOR_CONFIG={collector_config_yaml}"],
        "volumes": [traces_volume_mount],
        "mem_limit": f"{user_services_tracing_settings.USER_SERVICES_TRACING_COLLECTOR_MEMORY_LIMIT}",
        "cpus": f"{user_services_tracing_settings.USER_SERVICES_TRACING_COLLECTOR_CPU_LIMIT}",
        "cpu_shares": user_services_tracing_settings.USER_SERVICES_TRACING_COLLECTOR_CPU_SHARES,
        "stop_grace_period": (
            f"{int(user_services_tracing_settings.USER_SERVICES_TRACING_COLLECTOR_STOP_GRACE_PERIOD.total_seconds())}s"
        ),
    }
