---
name: update-webserver-rest-api
description: 'Update or add REST API endpoints for the web-server service. Use when: adding new endpoints, modifying request/response models, changing query/path/body parameters, updating OpenAPI specs, bumping web-server API version, regenerating openapi.json.'

---

# Update Web-Server REST API

## When to Use

- Adding a new REST endpoint to the web-server service
- Modifying request/response schemas (body, query, path parameters)
- Changing an endpoint path, method, or status code
- Regenerating the OpenAPI specification after any of the above

## Overview

The web-server REST API is defined in **two places** that must stay in sync:

1. **OpenAPI spec definitions** (`api/specs/web-server/`) — FastAPI router stubs used solely to generate the `openapi.json` file. These are NOT the real handlers.
2. **aiohttp implementation** (`services/web/server/src/simcore_service_webserver/`) — The actual request handlers registered with aiohttp routes.

A validation test ensures both sides match: handler names in aiohttp must correspond to `operationId` values in the generated OpenAPI spec.

## Procedure

### Step 1: Define or update the Pydantic schemas

Request/response models live in `packages/models-library/src/models_library/api_schemas_webserver/`.

- Input schemas (request bodies) inherit from `InputSchema`
- Output schemas (responses) inherit from `OutputSchema`
- Both are defined in `packages/models-library/src/models_library/api_schemas_webserver/_base.py`
- Query parameter models are plain `BaseModel` subclasses
- Field names use `snake_case` in Python; the `alias_generator` on `InputSchema`/`OutputSchema` auto-converts to `camelCase` for the JSON API
- Use existing files as reference (e.g. `users.py`, `auth.py`)

### Step 2: Add the FastAPI stub in `api/specs/web-server/`

Each endpoint group has its own module (e.g. `_users_admin.py`, `_auth.py`). Open the relevant file under `api/specs/web-server/` and add a FastAPI route stub.

Key conventions:
- The function name **must** match the aiohttp handler name (it becomes the `operationId`)
- Use `response_model=Envelope[...]` for JSON envelope responses, or `Page[...]` for paginated responses
- Use `status_code=status.HTTP_204_NO_CONTENT` for no-body responses
- Query parameters use the `as_query()` wrapper from `_common.py`: `_query: Annotated[as_query(MyQueryParams), Depends()]`
- Body parameters are just typed arguments: `_body: MyInputSchema`
- Path parameters use FastAPI path syntax in the route string
- The function body is just `...` (ellipsis) — these are stubs, not implementations

Example:
```python
from _common import as_query
from fastapi import APIRouter, Depends, status
from models_library.api_schemas_webserver.users import MyInput, MyOutput
from models_library.generics import Envelope

router = APIRouter(prefix=f"/{API_VTAG}", tags=["users"])

@router.post(
    "/admin/user-accounts:my-action",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["admin"],
)
async def my_action_on_user_account(_body: MyInput): ...

@router.get(
    "/admin/some-resource",
    response_model=Envelope[list[MyOutput]],
    tags=["admin"],
)
async def list_some_resource(): ...
```

Google API Design conventions (see https://cloud.google.com/apis/design):
- Standard methods: `list`, `get`, `create`, `update`, `delete`
- Custom methods use `:verb` suffix on the resource: `/resource:action`
- Collection-level custom methods: `POST /v0/admin/user-accounts:approve`
- Search is a custom method: `GET /v0/admin/user-accounts:search`

### Step 3: Implement the aiohttp handler

Handlers live under `services/web/server/src/simcore_service_webserver/`. Each domain has its own `_controller/rest/` directory.

Key conventions:
- Routes use `web.RouteTableDef()` and `@routes.get(...)` / `@routes.post(...)` decorators
- The `name=` parameter in the route decorator **must** match the FastAPI stub function name
- Handlers are decorated with `@login_required`, `@permission_required(...)` or `@group_or_role_permission_required(...)`, and `@handle_rest_requests_exceptions`
- Parse body with `parse_request_body_as(MyInputSchema, request)`
- Parse query with `parse_request_query_parameters_as(MyQueryParams, request)`
- Return responses with `envelope_json_response(data)` or `web.json_response(status=status.HTTP_204_NO_CONTENT)`
- For paginated endpoints, use `create_json_response_from_page(page)`

Example:
```python
@routes.post(f"/{API_VTAG}/admin/user-accounts:my-action", name="my_action_on_user_account")
@login_required
@group_or_role_permission_required("admin.users.write")
@handle_rest_requests_exceptions
async def my_action_on_user_account(request: web.Request) -> web.Response:
    body = await parse_request_body_as(MyInput, request)
    await my_service.do_action(request.app, ...)
    return web.json_response(status=status.HTTP_204_NO_CONTENT)
```

### Step 4: Map exceptions to HTTP errors

Domain exceptions are mapped to HTTP status codes in `_rest_exceptions.py` (usually at `_controller/rest/_rest_exceptions.py`). Add mappings for any new exceptions so they return proper HTTP error responses.

### Step 5: Bump the API version

From the `services/web/server/` directory:

```bash
cd services/web/server
make install-dev   # if not already done in this session
make version-minor # for new endpoints or backwards-compatible changes
# OR
make version-patch # for bug fixes only
```

- `version-minor` for adding new endpoints or changing behavior (backwards-compatible)
- `version-patch` for bug fixes that don't change the API surface

### Step 6: Regenerate the OpenAPI spec

From the same `services/web/server/` directory:

```bash
make openapi-specs
```

This runs the FastAPI stubs in `api/specs/web-server/` and writes the generated spec to `services/web/server/src/simcore_service_webserver/api/v0/openapi.json`. It also validates the spec.

After regeneration, verify that the new endpoints appear in the JSON file.

### Step 7: Run the OpenAPI validation test

```bash
pytest tests/unit/with_dbs/03/test__openapi_specs.py -v
```

This test creates the full aiohttp application and checks that every named route has a corresponding `operationId` in the OpenAPI spec. If a handler name doesn't match its FastAPI stub name, the test will fail.

## Checklist

- [ ] Pydantic schemas added/updated in `models-library`
- [ ] FastAPI stub added in `api/specs/web-server/_<module>.py`
- [ ] aiohttp handler implemented with matching `name=` parameter
- [ ] Exception-to-HTTP mappings added in `_rest_exceptions.py`
- [ ] Version bumped (`make version-minor` or `make version-patch`)
- [ ] OpenAPI spec regenerated (`make openapi-specs`)
- [ ] Validation test passes (`test__openapi_specs.py`)

## Common Mistakes

| Mistake | Symptom | Fix |
|---------|---------|-----|
| Handler `name=` doesn't match FastAPI stub function name | `test__openapi_specs` fails with missing route | Make both names identical |
| Forgot to run `make openapi-specs` | `openapi.json` is stale, test may pass but spec is wrong | Regenerate after any API change |
| Query model not wrapped in `as_query()` in FastAPI stub | Query params don't appear in generated spec | Use `Annotated[as_query(MyParams), Depends()]` |
| Using `InputSchema` for query params | `alias_generator` produces camelCase query params | Use plain `BaseModel` for query params |
| Editing `openapi.json` by hand | Changes overwritten on next `make openapi-specs` | Always edit the FastAPI stubs instead |


---
*Last updated: 2026-03-31*
