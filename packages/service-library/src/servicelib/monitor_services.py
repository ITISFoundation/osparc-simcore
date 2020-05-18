from enum import Enum
from typing import List, Union

from aiohttp import web
from prometheus_client import Counter
from prometheus_client.registry import CollectorRegistry

kSERVICE_STARTED = f"{__name__}.services_started"
kSERVICE_STOPPED = f"{__name__}.services_stopped"

SERVICE_STARTED_LABELS: List[str] = [
    "user_id",
    "project_id",
    "service_uuid",
    "service_key",
    "service_tag",
    "service_type",
]

SERVICE_STOPPED_LABELS: List[str] = [
    "user_id",
    "project_id",
    "service_uuid",
    "service_key",
    "service_tag",
    "service_type",
    "result",
]


def add_instrumentation(app: web.Application, reg: CollectorRegistry) -> None:

    app[kSERVICE_STARTED] = Counter(
        name="services_started_total",
        documentation="Counts the services started",
        labelnames=SERVICE_STARTED_LABELS,
        namespace="simcore",
        registry=reg,
    )

    app[kSERVICE_STOPPED] = Counter(
        name="services_stopped_total",
        documentation="Counts the services stopped",
        labelnames=SERVICE_STOPPED_LABELS,
        namespace="simcore",
        registry=reg,
    )


class ServiceResult(Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class ServiceType(Enum):
    COMPUTATIONAL = 0
    DYNAMIC = 1


def service_started(
    # pylint: disable=too-many-arguments
    app: web.Application,
    user_id: str,
    project_id: str,
    service_uuid: str,
    service_key: str,
    service_tag: str,
    service_type: Union[ServiceType, str],
) -> None:
    app[kSERVICE_STARTED].labels(
        user_id=user_id,
        project_id=project_id,
        service_uuid=service_uuid,
        service_key=service_key,
        service_tag=service_tag,
        service_type=service_type,
    ).inc()


def service_stopped(
    # pylint: disable=too-many-arguments
    app: web.Application,
    user_id: str,
    project_id: str,
    service_uuid: str,
    service_key: str,
    service_tag: str,
    service_type: Union[ServiceType, str],
    result: Union[ServiceResult, str],
) -> None:
    app[kSERVICE_STOPPED].labels(
        user_id=user_id,
        project_id=project_id,
        service_uuid=service_uuid,
        service_key=service_key,
        service_tag=service_tag,
        service_type=service_type,
        result=result.name if isinstance(result, ServiceResult) else result,
    ).inc()
