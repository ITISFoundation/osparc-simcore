---
applyTo: 'api/specs/web-server/**'
---

## Web-Server OpenAPI Spec Stubs

Files in `api/specs/web-server/` are **FastAPI stubs used only to generate `openapi.json`**. They are NOT the runtime implementation.

### Key Rules

1. **Stubs, not implementation**: These FastAPI route functions have empty bodies (e.g. `...`). The real handlers live in `services/web/server/src/simcore_service_webserver/` using aiohttp.
2. **`operationId` = function name**: The FastAPI function name becomes the `operationId` in the spec. The corresponding aiohttp route must use `name="operationId"` to match.
3. **Wrap query models with `as_query()`**: Import from `_common.py`. This unwraps Pydantic fields into individual query parameters in the spec.
4. **Response wrappers**: Use `Envelope[T]` for single-resource responses and `Page[T]` for paginated lists (from `models_library`).
5. **After any change here**: bump version and regenerate — see skill `update-webserver-rest-api`.

### Related Documents

- **[DESIGN.md](../../services/web/server/DESIGN.md)** — Web-server architecture, domain layer model, and design invariants. Reference when designing endpoint structure, choosing response models, or understanding service composition.
- **[TESTS.md](../../services/web/server/TESTS.md)** — Testing invariants and conventions. Reference when designing test fixtures or understanding how endpoints should be tested.
