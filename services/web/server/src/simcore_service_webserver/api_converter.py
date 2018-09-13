import logging

from aiohttp import web_exceptions

from . import director_sdk
from simcore_director_sdk.rest import ApiException

log = logging.getLogger(__file__)

async def convert_task_to_old_version(task):
    log.debug("converting task to old version %s", task)
    image_key = task["image"]
    try:
        services_enveloped = await director_sdk.get_director().services_by_key_version_get(image_key["name"], image_key["tag"])
    except ApiException as err:
        log.exception("Error while converting to old version:")
        raise web_exceptions.HTTPNotFound(reason=str(err))
    if not services_enveloped:
        raise web_exceptions.HTTPNotFound(reason="Could not retrieve service")
    node_details = services_enveloped.data[0]
    log.debug("retrieved service details: %s", node_details)
    # let's convert
    old_task = task
    old_task["input"] = __convert_ports_to_old_version(task["input"], node_details.inputs)
    old_task["output"] = __convert_ports_to_old_version(task["output"], node_details.outputs)
    log.debug("Completed conversion:%s", old_task)
    return old_task

def __convert_ports_to_old_version(ports, node_description):
    log.debug("converting ports from %s using description %s", ports, node_description)
    old_ports = []
    for port_key, port_data in ports.items():
        # sanitize port key (some old services define some keys with a . inside that is not accepted by the schema)
        #TODO: Remove this once the services are updated
        for key in node_description.keys():
            if str(key).startswith(port_key):
                port_key = key
                break
        # port_key = str(port_key).partition(".")[0]
        port_description = node_description[port_key]
        old_port = {
            "key":port_key,
            "label":port_description["label"],
            "desc":port_description["description"],
            "type":port_description["type"]
        }
        if port_description["type"] == "data:*/*":
            old_port["type"] = "file-url"
        elif port_description["type"] == "data:application/zip":
            old_port["type"] = "folder-url"

        old_port["value"] = port_data
        if isinstance(port_data, dict):
            old_port["value"] = "null"
            if "nodeUuid" in port_data and "output" in port_data:
                old_port["value"] = str(".").join(["link", port_data["nodeUuid"], port_data["output"]])
        old_ports.append(old_port)
    return old_ports
