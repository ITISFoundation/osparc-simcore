import urllib.parse

from models_library.services import ServiceType


def get_service_from_key(service_key: str) -> ServiceType:
    decoded_service_key = urllib.parse.unquote_plus(service_key)
    encoded_service_type = decoded_service_key.split("/")[2]
    if encoded_service_type == "comp":
        encoded_service_type = "computational"
    return ServiceType(encoded_service_type)
