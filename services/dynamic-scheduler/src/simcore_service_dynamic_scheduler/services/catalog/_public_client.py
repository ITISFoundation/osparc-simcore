from fastapi import FastAPI
from models_library.api_schemas_catalog.services_specifications import (
    ServiceSpecifications,
)
from models_library.service_settings_labels import SimcoreServiceLabels
from models_library.services import ServiceKey, ServiceVersion
from models_library.users import UserID
from pydantic import TypeAdapter
from servicelib.fastapi.app_state import SingletonInAppStateMixin

from ._thin_client import CatalogThinClient


class CatalogPublicClient(SingletonInAppStateMixin):
    app_state_name: str = "catalog_public_client"

    def __init__(self, app: FastAPI) -> None:
        self.app = app

    async def get_services_labels(
        self, service_key: ServiceKey, service_version: ServiceVersion
    ) -> SimcoreServiceLabels:
        response = await CatalogThinClient.get_from_app_state(
            self.app
        ).get_services_labels(service_key, service_version)
        return TypeAdapter(SimcoreServiceLabels).validate_python(response.json())

    async def get_services_specifications(
        self, user_id: UserID, service_key: ServiceKey, service_version: ServiceVersion
    ) -> ServiceSpecifications:
        response = await CatalogThinClient.get_from_app_state(
            self.app
        ).get_services_specifications(user_id, service_key, service_version)
        return TypeAdapter(ServiceSpecifications).validate_python(response.json())
