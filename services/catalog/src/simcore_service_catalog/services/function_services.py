# mypy: disable-error-code=truthy-function
from typing import Any

from fastapi import status
from fastapi.applications import FastAPI
from fastapi.exceptions import HTTPException
from models_library.function_services_catalog import (
    is_function_service,
    iter_service_docker_data,
)
from models_library.services import ServiceMetaDataPublished

assert is_function_service  # nosec


def _as_dict(model_instance: ServiceMetaDataPublished) -> dict[str, Any]:
    return model_instance.model_dump(by_alias=True, exclude_unset=True)


def get_function_service(key, version) -> ServiceMetaDataPublished:
    try:
        return next(
            s
            for s in iter_service_docker_data()
            if s.key == key and s.version == version
        )
    except StopIteration as err:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Frontend service '{key}:{version}' not found",
        ) from err


def setup_function_services(app: FastAPI):
    def _on_startup() -> None:
        catalog = [_as_dict(metadata) for metadata in iter_service_docker_data()]
        app.state.frontend_services_catalog = catalog

    app.add_event_handler("startup", _on_startup)


__all__: tuple[str, ...] = (
    "get_function_service",
    "is_function_service",
    "setup_function_services",
)
