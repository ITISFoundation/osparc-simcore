import datetime
import json
import logging
from typing import Any

import arrow
from fastapi import FastAPI
from models_library.users import UserID
from prometheus_api_client import PrometheusConnect
from simcore_service_resource_usage_tracker.modules.prometheus import (
    get_prometheus_api_client,
)

#####
# This is just a placeholder script with original DevOps provided script, will be modified in upcoming PRs
# Unit tests are already prepared and running.
#####

_logger = logging.getLogger(__name__)


def _assure_dict_entry_exists(
    metric_data, max_values_per_docker_id, image, userid
) -> None:
    for metric in metric_data:
        current_id = metric["metric"]["id"]
        if current_id not in max_values_per_docker_id.keys():
            max_values_per_docker_id[current_id] = {
                "container_uuid": metric["metric"]["container_label_uuid"],
                "cpu_seconds": 0,
                "uptime_minutes": 0,
                "nano_cpu_limits": 0,
                "egress_bytes": 0,
                "image": image,
                "user_id": userid,
            }


async def _evaluate_service_resource_usage(
    prometheus_client: PrometheusConnect,
    start_time: datetime.datetime,
    stop_time: datetime.datetime,
    user_id: UserID,
    uuid: str = ".*",
    image: str = "registry.osparc.io/simcore/services/dynamic/jupyter-smash:3.0.9",
) -> dict[str, Any]:
    max_values_per_docker_id: dict[str, Any] = {}
    time_delta = stop_time - start_time
    minutes = round(time_delta.total_seconds() / 60)

    for current_datetime in [
        stop_time - datetime.timedelta(minutes=i) for i in range(minutes)
    ]:
        rfc3339_str = current_datetime.isoformat("T")
        # Query CPU seconds
        promql_cpu_query = f"sum without (cpu) (container_cpu_usage_seconds_total{{container_label_user_id='{user_id}',image='{image}',container_label_uuid=~'{uuid}'}})"
        container_cpu_seconds_usage = prometheus_client.custom_query(
            promql_cpu_query, params={"time": rfc3339_str}
        )
        # Query network egress
        promql_network_query = f"container_network_transmit_bytes_total{{container_label_user_id='{user_id}',image='{image}',container_label_uuid=~'{uuid}'}}"
        container_network_egress = prometheus_client.custom_query(
            promql_network_query, params={"time": rfc3339_str}
        )

        if container_cpu_seconds_usage:
            _assure_dict_entry_exists(
                container_cpu_seconds_usage, max_values_per_docker_id, image, user_id
            )
            metric_data = container_cpu_seconds_usage
            for metric in metric_data:
                current_id = metric["metric"]["id"]
                if (
                    float(metric["value"][-1])
                    > max_values_per_docker_id[current_id]["cpu_seconds"]
                ):
                    max_values_per_docker_id[current_id]["cpu_seconds"] = float(
                        metric["value"][-1]
                    )
        if container_network_egress:
            _assure_dict_entry_exists(
                container_network_egress, max_values_per_docker_id, image, user_id
            )
            metric_data = container_network_egress
            for metric in metric_data:
                current_id = metric["metric"]["id"]
                if (
                    float(metric["value"][-1])
                    > max_values_per_docker_id[current_id]["cpu_seconds"]
                ):
                    max_values_per_docker_id[current_id]["egress_bytes"] = float(
                        metric["value"][-1]
                    )
        if container_network_egress or container_cpu_seconds_usage:
            metric_data = container_network_egress
            for metric in metric_data:
                current_id = metric["metric"]["id"]
                if float(metric["value"][-1]):
                    # For every point in time (granularity: minutes) where we find a timeseries, we assume the
                    # service ran for the incremental unit of 1 minute
                    max_values_per_docker_id[current_id]["uptime_minutes"] += 1

                # Get CPU Limits from docker container labels
                simcore_service_settings = metric["metric"][
                    "container_label_simcore_service_settings"
                ]
                simcore_service_settings = json.loads(simcore_service_settings)
                simcore_service_settings_resources = [
                    i
                    for i in simcore_service_settings
                    if "name" in i.keys() and "Resources" in i.values()
                ][0]
                nano_cpu_limits = int(
                    simcore_service_settings_resources["value"]["Limits"]["NanoCPUs"]
                )
                max_values_per_docker_id[current_id][
                    "nano_cpu_limits"
                ] = nano_cpu_limits
    return max_values_per_docker_id


async def collect_and_return_service_resource_usage(
    prometheus_client: PrometheusConnect, user_id: UserID
) -> dict[str, Any]:
    now = arrow.utcnow().datetime
    data = await _evaluate_service_resource_usage(
        prometheus_client, now - datetime.timedelta(hours=1), now, user_id=user_id
    )
    _logger.info(json.dumps(data, indent=2, sort_keys=True))
    return data


async def collect_service_resource_usage_task(app: FastAPI) -> None:
    await collect_and_return_service_resource_usage(
        get_prometheus_api_client(app), 43817
    )
