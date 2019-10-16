from ..login.decorators import login_required
import aiohttp
from urllib.parse import quote
import asyncio
import json

@login_required
async def get_status(request: aiohttp.web.Request):
    async with aiohttp.ClientSession() as session:
        cpu_query = 'sum by (container_label_node_id) (irate(container_cpu_usage_seconds_total{container_label_node_id=~".+"}[30s]) * 100)'
        memory_query = 'sum by (container_label_node_id) (container_memory_usage_bytes{container_label_node_id=~".+"} / 1000000)'
        url = 'http://prometheus:9090/api/v1/query'

        async def get_cpu_usage():
            async with session.get(url + '?query=' + quote(cpu_query)) as resp:
                status = resp.status
                result = await resp.text()
                return result

        async def get_memory_usage():
            async with session.get(url + '?query=' + quote(memory_query)) as resp:
                status = resp.status
                result = await resp.text()
                return result

        results = await asyncio.gather(get_cpu_usage(), get_memory_usage())
        json_results = list(map(json.loads, results))
        return {
            'error': None,
            'data': {
                'stats': {
                    'cpuUsage': 0,
                    'memoryUsage': 0
                },
                'result': json_results
            }
        }
