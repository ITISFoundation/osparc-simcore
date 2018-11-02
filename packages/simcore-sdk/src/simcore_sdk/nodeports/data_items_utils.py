from . import config

def is_value_link(item_value):
    # a link is composed of {nodeUuid:uuid, output:port_key}
    return isinstance(item_value, dict) and all(k in item_value for k in ("nodeUuid", "output"))

def is_value_on_store(item_value):
    return isinstance(item_value, dict) and all(k in item_value for k in ("store", "path"))

def is_file_type(item_type):
    return str(item_type).startswith(config.FILE_TYPE_PREFIX)

def decode_link(value):
    return value["nodeUuid"], value["output"]

def decode_store(value):
    return value["store"], value["path"]

def encode_store(store, s3_object):
    return {"store":store, "path":s3_object}