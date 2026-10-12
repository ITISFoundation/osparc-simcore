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
3. For Pydantic models representing query parameters, use
   `Annotated[as_query(QueryModel), Depends()]`, importing `as_query` from
   `._common`. This exposes each field as an individual query parameter.
   Do not apply `as_query()` to path, header, cookie, or request-body models;
   `Depends()` alone does not identify a query model.
4. Use `Envelope[T]` for single resources and `Page[T]` for paginated lists
   (from `models_library`).
