import json
from datetime import datetime, timedelta

from prometheus_api_client import PrometheusConnect

# create PrometheusConnect object with remote URL
prom = PrometheusConnect(url="http://user:pass@monitoring.osparc.io/prometheus")

# This script assumes everywhere that the minimum granularity of the data is 1 minute
# Setting it smaller is unreasonable at least for prometheus, as the scraping interval is apprx. eq. to 1 h


def assureDictEntryExists(metric_data, max_values_per_docker_id, image, userid):
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


def evaluate_service_resource_usage(
    starttime: datetime,
    stoptime: datetime,
    userid: int,
    uuid: str = ".*",
    image: str = "registry.osparc.io/simcore/services/dynamic/jupyter-smash:3.0.9",
):
    max_values_per_docker_id = {}
    td = stoptime - starttime
    minutes = int(td.total_seconds() / 60)
    for currentDatetime in [stoptime - timedelta(minutes=i) for i in range(minutes)]:
        rfc3339_str = currentDatetime.isoformat("T") + "-00:00"
        # Query CPU seconds
        promql_cpu_query = f"sum without (cpu) (container_cpu_usage_seconds_total{{container_label_user_id='{userid}',image='{image}',container_label_uuid=~'{uuid}'}})"
        container_cpu_seconds_usage = prom.custom_query(
            promql_cpu_query, params={"time": rfc3339_str}
        )
        # Query network egress
        promql_network_query = f"container_network_transmit_bytes_total{{container_label_user_id='{userid}',image='{image}',container_label_uuid=~'{uuid}'}}"
        container_network_egress = prom.custom_query(
            promql_network_query, params={"time": rfc3339_str}
        )

        if container_cpu_seconds_usage:
            assureDictEntryExists(
                container_cpu_seconds_usage, max_values_per_docker_id, image, userid
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
            assureDictEntryExists(
                container_network_egress, max_values_per_docker_id, image, userid
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


now = datetime.utcnow()
data = evaluate_service_resource_usage(
    now - timedelta(hours=1), now, userid="43817"
)  # This userid is puppeteer1 on osparc.io
print(json.dumps(data, indent=4, sort_keys=True))
