from aiohttp import web
from ..login.decorators import login_required
import aiohttp

@login_required
async def get_status(request: web.Request):
    async with aiohttp.ClientSession() as session:
        async with session.get('http://127.0.0.1:9090/api/v1/query?query=irate%28container_cpu_user_seconds_total%7Bcontainer_label_user_id%3D~%22.%2B%22%7D%5B12s%5D%29%20%2A%20100') as resp:
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
