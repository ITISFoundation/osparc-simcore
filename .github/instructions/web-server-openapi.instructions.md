---
applyTo: 'api/specs/web-server/**'
---

# Web-server OpenAPI spec stubs

Files in `api/specs/web-server/` are FastAPI stubs used only to generate
`openapi.json`; they are not the runtime implementation.

1. Route functions have empty bodies (`...`). The real aiohttp handlers live in
   `services/web/server/src/simcore_service_webserver/`.
2. The function name becomes the `operationId`; the aiohttp route must use
   `name="<operationId>"`.
3. For each route whose parameters are declared as a Pydantic model via
   `Depends()` or `Query()`, wrap that model with `as_query()` from
   `api/specs/web-server/_common.py` (import as `from ._common import as_query`)
   so each field becomes an individual query parameter. Do not wrap request
   body models.
4. Use `Envelope[T]` for single resources and `Page[T]` for paginated lists
   (from `models_library`).
