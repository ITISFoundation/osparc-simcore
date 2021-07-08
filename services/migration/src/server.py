from fastapi import FastAPI
from fastapi.responses import PlainTextResponse

MIGRATION_OK: str = "42"

app = FastAPI()


@app.get(
    "/",
    include_in_schema=False,
    response_class=PlainTextResponse,
    description=(
        "Empty route used by entrypoint.sh scripts in "
        "docker images to check if service is available."
        "when this service is ready it means Postgres is "
        "available and all migrations have finished."
    ),
)
async def can_start_other_services_in_stack() -> str:
    return MIGRATION_OK
