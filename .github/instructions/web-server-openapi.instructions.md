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
3. Wrap query models with `as_query()` from `_common.py` so fields become
   individual query parameters.
4. Use `Envelope[T]` for single resources and `Page[T]` for paginated lists
   (from `models_library`).
