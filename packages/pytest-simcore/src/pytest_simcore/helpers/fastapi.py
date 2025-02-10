import httpx
from fastapi import FastAPI
from yarl import URL


def url_from_operation_id(
    client: httpx.AsyncClient, app: FastAPI, operation_id: str, **path_params
) -> URL:
    return URL(f"{client.base_url}").with_path(
        app.url_path_for(operation_id, **path_params)
    )
