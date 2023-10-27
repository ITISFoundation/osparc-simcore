from fastapi import FastAPI
from models_library.api_schemas_directorv2.dynamic_services_service import (
    RunningDynamicServiceDetails,
)


# TODO: WITH PC figure out how to propagete the states
async def publish_update(app: FastAPI, status: RunningDynamicServiceDetails) -> None:
    # publishes a message via socketio
    ...
