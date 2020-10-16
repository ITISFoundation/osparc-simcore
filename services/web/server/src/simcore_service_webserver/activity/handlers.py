import asyncio
from collections import defaultdict

import aiohttp
from yarl import URL

from servicelib.application_keys import APP_CONFIG_KEY
from servicelib.client_session import get_client_session
from servicelib.request_keys import RQT_USERID_KEY

from ..computation_api import get_celery
from ..login.decorators import login_required


async def query_prometheus(session, url, query):
    async with session.get(url.with_query(query=query)) as resp:
        result = await resp.json()
        return result


def celery_reserved(app):
    return get_celery(app).control.inspect().reserved()


#
# Functions getting the data to be executed async
#
async def get_cpu_usage(session, url, user_id):
    cpu_query = f'sum by (container_label_node_id) (irate(container_cpu_usage_seconds_total{{container_label_node_id=~".+", container_label_user_id="{user_id}"}}[20s])) * 100'
    return await query_prometheus(session, url, cpu_query)


async def get_memory_usage(session, url, user_id):
    memory_query = f'container_memory_usage_bytes{{container_label_node_id=~".+", container_label_user_id="{user_id}"}} / 1000000'
    return await query_prometheus(session, url, memory_query)


async def get_celery_reserved(app):
    return celery_reserved(app)


async def get_container_metric_for_labels(session, url, user_id):
    just_a_metric = f'container_cpu_user_seconds_total{{container_label_node_id=~".+", container_label_user_id="{user_id}"}}'
    return await query_prometheus(session, url, just_a_metric)


def get_prometheus_result_or_default(result, default):
    if isinstance(result, Exception):
        # Logs exception
        return default
    return result["data"]["result"]


@login_required
async def get_status(request: aiohttp.web.Request):
    session = get_client_session(request.app)

    user_id = request.get(RQT_USERID_KEY, -1)

    config = request.app[APP_CONFIG_KEY]["activity"]
    url = (
        URL(config.get("prometheus_host"))
        .with_port(config.get("prometheus_port"))
        .with_path("api/" + config.get("prometheus_api_version") + "/query")
    )
    results = await asyncio.gather(
        get_cpu_usage(session, url, user_id),
        get_memory_usage(session, url, user_id),
        get_celery_reserved(request.app),
        get_container_metric_for_labels(session, url, user_id),
        return_exceptions=True,
    )
    cpu_usage = get_prometheus_result_or_default(results[0], [])
    mem_usage = get_prometheus_result_or_default(results[1], [])
    metric = get_prometheus_result_or_default(results[3], [])
    celery_inspect = results[2]

    res = defaultdict(dict)
    for node in cpu_usage:
        node_id = node["metric"]["container_label_node_id"]
        usage = float(node["value"][1])
        res[node_id] = {"stats": {"cpuUsage": usage}}

    for node in mem_usage:
        node_id = node["metric"]["container_label_node_id"]
        usage = float(node["value"][1])
        if node_id in res:
            res[node_id]["stats"]["memUsage"] = usage
        else:
            res[node_id] = {"stats": {"memUsage": usage}}

    for node in metric:
        limits = {"cpus": 0, "mem": 0}
        metric_labels = node["metric"]
        limits["cpus"] = float(
            metric_labels.get("container_label_nano_cpus_limit", 0)
        ) / pow(
            10, 9
        )  # Nanocpus to cpus
        limits["mem"] = float(metric_labels.get("container_label_mem_limit", 0)) / pow(
            1024, 2
        )  # In MB
        node_id = metric_labels.get("container_label_node_id")
        res[node_id]["limits"] = limits

    if hasattr(celery_inspect, "items"):
        for dummy_worker_id, worker in celery_inspect.items():
            for task in worker:
                values = task["args"][1:-1].split(", ")
                if values[0] == str(user_id):  # Extracts user_id from task's args
                    node_id = values[2][1:-1]  # Extracts node_id from task's args
                    res[node_id]["queued"] = True

    if not res:
        raise aiohttp.web.HTTPNoContent

    return dict(res)
