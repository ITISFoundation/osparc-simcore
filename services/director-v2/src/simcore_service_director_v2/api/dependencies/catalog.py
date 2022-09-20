from fastapi import Request

from ...modules.catalog import CatalogClient


def get_catalog_client(request: Request) -> CatalogClient:
    client = CatalogClient.instance(request.app)
    return client
