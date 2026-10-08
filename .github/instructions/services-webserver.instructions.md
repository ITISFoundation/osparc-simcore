---
applyTo: '**/services/web/server/**/*.py'
---

# Web-server (aiohttp) instructions

## aiohttp

- Use typed `web.AppKey` objects, not string keys, for application and request
  storage, with the most precise value type available:
  `APP_SETTINGS_KEY: Final = web.AppKey("APP_SETTINGS_KEY", ApplicationSettings)`.
- Follow the service's middleware, routing, and exception-handling patterns;
  use `web.RouteTableDef()` where that is the local route convention.

## Related documents

- [DESIGN.md](../../services/web/server/docs/DESIGN.md): architecture, domain
  layers, and design invariants. Read before designing endpoint structure,
  response models, or service composition.
- [TESTS.md](../../services/web/server/docs/TESTS.md): testing invariants. Read
  before designing test fixtures or endpoint tests.
