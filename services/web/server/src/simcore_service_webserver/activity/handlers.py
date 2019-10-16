from aiohttp import web
from ..login.decorators import login_required
import aiohttp
from urllib.parse import quote

@login_required
async def get_status(request: web.Request):
    async with aiohttp.ClientSession() as session:
        query = 'sum by (container_label_node_id) (irate(container_cpu_usage_seconds_total{container_label_node_id=~".+"}[30s]) * 100)'
        url = 'http://prometheus:9090/api/v1/query?query=' + quote(query)
        async with session.get(url) as resp:
            status = resp.status
            result = await resp.text()
            return {
                'error': None,
                'data': {
                    'stats': {
                        'cpuUsage': 0,
                        'memoryUsage': 0
                    },
                    'result': result
                }
            }
