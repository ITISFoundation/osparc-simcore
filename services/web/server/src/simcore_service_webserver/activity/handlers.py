from aiohttp import web
from ..login.decorators import login_required

@login_required
async def get_status(request: web.Request):
    
    return {
        'error': None,
        'data': {
            'stats': {
                'cpuUsage': 0,
                'memoryUsage': 0
            },
            'text': 'your mamma'
        }
    }
