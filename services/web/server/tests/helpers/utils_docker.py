
import logging

import docker
from tenacity import after_log, retry, stop_after_attempt, wait_fixed

log = logging.getLogger(__name__)

@retry(
    wait=wait_fixed(2),
    stop=stop_after_attempt(10),
    after=after_log(log, logging.WARN))
def get_service_published_port(service_name: str) -> str:
    # WARNING: ENSURE that service name defines a port
    # NOTE: retries since services can take some time to start
    client = docker.from_env()
    services = [x for x in client.services.list() if service_name in x.name]
    if not services:
        raise RuntimeError("Cannot find published port for service '%s'. Probably services still not up" % service_name)
    service_endpoint = services[0].attrs["Endpoint"]

    if "Ports" not in service_endpoint or not service_endpoint["Ports"]:
        raise RuntimeError("Cannot find published port for service '%s' in endpoint. Probably services still not up" % service_name)

    published_port = service_endpoint["Ports"][0]["PublishedPort"]
    return str(published_port)
