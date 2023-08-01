import aiohttp
import aiohttp.web
from yarl import URL


async def query_prometheus(session: aiohttp.ClientSession, url: URL, query: str):
    async with session.get(url.with_query(query=query)) as resp:
        return await resp.json()


async def get_cpu_usage(session, url, user_id):
    cpu_query = f'sum by (container_label_node_id) (irate(container_cpu_usage_seconds_total{{container_label_node_id=~".+", container_label_user_id="{user_id}"}}[20s])) * 100'
    return await query_prometheus(session, url, cpu_query)


async def get_memory_usage(session, url, user_id):
    memory_query = f'container_memory_usage_bytes{{container_label_node_id=~".+", container_label_user_id="{user_id}"}} / 1000000'
    return await query_prometheus(session, url, memory_query)


async def get_container_metric_for_labels(session, url, user_id):
    just_a_metric = f'container_cpu_user_seconds_total{{container_label_node_id=~".+", container_label_user_id="{user_id}"}}'
    return await query_prometheus(session, url, just_a_metric)


def get_prometheus_result_or_default(result, default):
    if isinstance(result, Exception):
        # Logs exception
        return default
    return result["data"]["result"]
