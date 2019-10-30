import asyncio

import aiohttp
from application_setup import get_client
from servicelib.client_session import get_client_session
from servicelib.request_keys import RQT_USERID_KEY
from yarl import URL

from ..computation_handlers import get_celery
from ..login.decorators import login_required


@login_required
async def get_status(request: aiohttp.web.Request):

    session = get_client_session(request.app)

    user_id = request.get(RQT_USERID_KEY, -1)

    cpu_query = f'irate(container_cpu_usage_seconds_total{{container_label_node_id=~".+", container_label_user_id="{str(user_id)}"}}[20s]) * 100'
    memory_query = f'container_memory_usage_bytes{{container_label_node_id=~".+", container_label_user_id="{str(user_id)}"}} / 1000000'
    just_a_metric = f'container_cpu_user_seconds_total{{container_label_node_id=~".+", container_label_user_id="{str(user_id)}"}}'
    
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

    async def get_celery_reserved():
        return get_celery(request.app).control.inspect().reserved()

    async def get_container_metric_for_labels():
        async with session.get(url.with_query(query=just_a_metric)) as resp:
            result = await resp.json()
            return result

    results = await asyncio.gather(get_cpu_usage(), get_memory_usage(), get_celery_reserved(), get_container_metric_for_labels())
    cpu_usage = results[0]['data']['result']
    mem_usage = results[1]['data']['result']
    metric = results[3]['data']['result']
    celery_inspect = results[2]

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
        if node_id in res:
            res[node_id]['stats']['memUsage'] = usage
        else:
            res[node_id] = {
                'stats': {
                    'memUsage': usage
                }
            }

    for node in metric:
        limits = {
            'cpus': 0,
            'mem': 0
        }
        metric_labels = node['metric']
        limits['cpus'] = float(metric_labels.get('container_label_nano_cpus', 0)) / pow(10, 9) # Nanocpus to cpus
        limits['mem'] = float(metric_labels.get('container_label_mem_limit', 0)) / pow(1024, 2) # In MB
        node_id = metric_labels.get('container_label_node_id')
        res[node_id]['limits'] = limits


    for dummy_worker_id, worker in celery_inspect.items():
        for task in worker:
            node_id = task['args'][1:-1].split(', ')[2][1:-1] # Extracts node_id from task's args
            if node_id in res:
                res[node_id]['queued'] = True
            else:
                res[node_id] = {
                    'queued': True
                }
    
    return res
