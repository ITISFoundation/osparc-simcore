from typing import Any, Final

# Web-server API responses of /projects/{project_id}/metadata/ports
# as reponses in this mock. SEE services/web/server/tests/unit/with_dbs/02/test__handlers__ports.py
# NOTE: this could be added as examples in the OAS but for the moment we want to avoid overloading openapi.yml
# in the web-server.
PROJECTS_METADATA_PORTS_RESPONSE_BODY_DATA: Final[list[dict[str, Any]]] = [
    {
        "key": "38a0d401-af4b-4ea7-ab4c-5005c712a546",
        "kind": "input",
        "content_schema": {
            "description": "Input integer value",
            "title": "X",
            "type": "integer",
        },
    },
    {
        "key": "fc48252a-9dbb-4e07-bf9a-7af65a18f612",
        "kind": "input",
        "content_schema": {
            "description": "Input integer value",
            "title": "Z",
            "type": "integer",
        },
    },
    {
        "key": "7bf0741f-bae4-410b-b662-fc34b47c27c9",
        "kind": "input",
        "content_schema": {
            "description": "Input boolean value",
            "title": "on",
            "type": "boolean",
        },
    },
    {
        "key": "09fd512e-0768-44ca-81fa-0cecab74ec1a",
        "kind": "output",
        "content_schema": {
            "description": "Output integer value",
            "title": "Random sleep interval_2",
            "type": "integer",
        },
    },
    {
        "key": "76f607b4-8761-4f96-824d-cab670bc45f5",
        "kind": "output",
        "content_schema": {
            "description": "Output integer value",
            "title": "Random sleep interval",
            "type": "integer",
        },
    },
]
