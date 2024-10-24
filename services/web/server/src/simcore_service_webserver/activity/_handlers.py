import asyncio
from collections import defaultdict

import aiohttp
import aiohttp.web
from models_library.api_schemas_webserver.activity import ActivityStatusDict
from pydantic import TypeAdapter
from servicelib.aiohttp.client_session import get_client_session
from servicelib.mimetype_constants import MIMETYPE_APPLICATION_JSON
from servicelib.request_keys import RQT_USERID_KEY
from yarl import URL

from .._meta import API_VTAG
from ..login.decorators import login_required
from ._api import (
    get_container_metric_for_labels,
    get_cpu_usage,
    get_memory_usage,
    get_prometheus_result_or_default,
)
from .settings import get_plugin_settings

routes = aiohttp.web.RouteTableDef()


@routes.get(f"/{API_VTAG}/activity/status", name="get_activity_status")
@login_required
async def get_activity_status(request: aiohttp.web.Request):
    session = get_client_session(request.app)
    user_id = request.get(RQT_USERID_KEY, -1)

    prometheus_settings = get_plugin_settings(request.app)
    url = URL(prometheus_settings.base_url)

    results = await asyncio.gather(
        get_cpu_usage(session, url, user_id),
        get_memory_usage(session, url, user_id),
        get_container_metric_for_labels(session, url, user_id),
        return_exceptions=True,
    )
    cpu_usage = get_prometheus_result_or_default(results[0], [])
    mem_usage = get_prometheus_result_or_default(results[1], [])
    metric = get_prometheus_result_or_default(results[2], [])

    res: dict = defaultdict(dict)
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
        limits = {"cpus": 0.0, "mem": 0.0}
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

    if not res:
        raise aiohttp.web.HTTPNoContent(content_type=MIMETYPE_APPLICATION_JSON)

    assert TypeAdapter(ActivityStatusDict).validate_python(res) is not None  # nosec
    return dict(res)
