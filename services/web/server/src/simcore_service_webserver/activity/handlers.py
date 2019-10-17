import asyncio

import aiohttp
from yarl import URL

from ..login.decorators import login_required


@login_required
async def get_status(request: aiohttp.web.Request):

    async with aiohttp.ClientSession() as session:
        cpu_query = 'sum by (container_label_node_id) (irate(container_cpu_usage_seconds_total{container_label_node_id=~".+"}[30s]) * 100)'
        memory_query = 'sum by (container_label_node_id) (container_memory_usage_bytes{container_label_node_id=~".+"} / 1000000)'
        
        config = request.app['servicelib.application_keys.config']['activity']
        url = URL(config.get('prometheus_host')).with_port(config.get('prometheus_port')).with_path('api/' + config.get('prometheus_api_version') + '/query')

        async def get_cpu_usage():
            async with session.get(url.with_query(query=cpu_query)) as resp:
                result = await resp.json()
                return result

        async def get_memory_usage():
            async with session.get(url.with_query(query=memory_query)) as resp:
                result = await resp.json()
                return result

        results = await asyncio.gather(get_cpu_usage(), get_memory_usage())
        cpu_usage = results[0]['data']['result']
        mem_usage = results[1]['data']['result']

        res = {}
        for node in cpu_usage:
            node_id = node['metric']['container_label_node_id']
            usage = node['value'][1]
            res[node_id] = {
                'stats': {
                    'cpuUsage': usage
                }
            }

        for node in mem_usage:
            node_id = node['metric']['container_label_node_id']
            usage = node['value'][1]
            res[node_id]['stats']['memUsage'] = usage
        
        return res
