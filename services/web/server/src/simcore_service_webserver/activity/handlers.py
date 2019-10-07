from aiohttp import web
from ..login.decorators import login_required
import docker
import concurrent.futures
import json

@login_required
async def get_status(request: web.Request):

    def get_container_stats(container):
        return container.stats(decode=False, stream=False)

    def get_container_list():
        client = docker.from_env()
        return client.containers.list(all=True)

    def filter_fun(container):
        if container.labels.get('io.simcore.type'):
            container_type = json.loads(container.labels.get('io.simcore.type')).get('type')
            return container_type == 'computational' or container_type == 'dynamic'
        return False

    containers = list(filter(filter_fun, get_container_list()))

    def calculate_cpu_usage_linux(container_stats):
        cpu = 0
        previous_cpu = container_stats['precpu_stats']['cpu_usage']['total_usage']
        previous_system = container_stats['precpu_stats']['system_cpu_usage']
        cpu_delta = container_stats['cpu_stats']['cpu_usage']['total_usage'] - previous_cpu
        system_delta = container_stats['cpu_stats']['system_cpu_usage'] - previous_system

        if system_delta > 0 and cpu_delta > 0:
            cpu = (cpu_delta / system_delta) * len(container_stats['cpu_stats']['cpu_usage']['percpu_usage']) * 100

        return cpu

    with concurrent.futures.ThreadPoolExecutor() as executor:
        stats = list(zip(containers, executor.map(get_container_stats, containers)))

    ret = {}
    for duple in stats:
        cont = duple[0]
        container_id = cont.labels.get('com.docker.swarm.service.id')
        stat = duple[1]
        ret[container_id] = {}
        ret[container_id]['key'] = json.loads(cont.labels.get('io.simcore.key')).get('key')
        ret[container_id]['name'] = json.loads(cont.labels.get('io.simcore.name')).get('name')
        ret[container_id]['stats'] = {}
        ret[container_id]['stats']['cpuUsage'] = calculate_cpu_usage_linux(stat)
    
    return {
        'error': None,
        'data': ret
    }
