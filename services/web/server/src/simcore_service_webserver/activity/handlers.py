import asyncio

import aiohttp
from servicelib.client_session import get_client_session
from servicelib.request_keys import RQT_USERID_KEY
from yarl import URL

from ..computation_handlers import get_celery
from ..login.decorators import login_required

from servicelib.application_keys import APP_CONFIG_KEY # ??

async def get_cpu_usage(session, url, user_id):
    cpu_query = f'irate(container_cpu_usage_seconds_total{{container_label_node_id=~".+", container_label_user_id="{user_id}"}}[20s]) * 100'
    async with session.get(url.with_query(query=cpu_query)) as resp:
        result = await resp.json()
        return result

async def get_memory_usage(session, url, user_id):
    memory_query = f'container_memory_usage_bytes{{container_label_node_id=~".+", container_label_user_id="{user_id}"}} / 1000000'
    async with session.get(url.with_query(query=memory_query)) as resp:
        result = await resp.json()
        return result

async def get_celery_reserved(app):
    return get_celery(app).control.inspect().reserved()

async def get_container_metric_for_labels(session, url, user_id):
    just_a_metric = f'container_cpu_user_seconds_total{{container_label_node_id=~".+", container_label_user_id="{user_id}"}}'
    async with session.get(url.with_query(query=just_a_metric)) as resp:
        result = await resp.json()
        return result

@login_required
async def get_status(request: aiohttp.web.Request):

    session = get_client_session(request.app)

    user_id = request.get(RQT_USERID_KEY, -1)


    config = request.app[APP_CONFIG_KEY]['activity']
    url = URL(config.get('prometheus_host')).with_port(config.get('prometheus_port')).with_path('api/' + config.get('prometheus_api_version') + '/query')

    results = await asyncio.gather(
        get_cpu_usage(session, url, user_id),
        get_memory_usage(session, url, user_id),
        get_celery_reserved(request.app),
        get_container_metric_for_labels(session, url, user_id)
    )
    cpu_usage = results[0]['data']['result']
    mem_usage = results[1]['data']['result']
    metric = results[3]['data']['result']
    celery_inspect = results[2]

    res = {}
    for node in cpu_usage:
        node_id = node['metric']['container_label_node_id']
        usage = float(node['value'][1])
        res[node_id] = {
            'stats': {
                'cpuUsage': usage
            }
        }

    for node in mem_usage:
        node_id = node['metric']['container_label_node_id']
        usage = float(node['value'][1])
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
        limits['cpus'] = float(metric_labels.get('container_label_nano_cpus_limit', 0)) / pow(10, 9) # Nanocpus to cpus
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
