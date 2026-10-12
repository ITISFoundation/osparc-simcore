---
applyTo: '**/packages/service-library/**/*.py,**/services/web/server/**/*.py'
---

# aiohttp instructions

Only when modifying aiohttp code in the webserver or shared service library.

- Use typed `web.AppKey` objects, not string keys, for application and request
  storage, with the most precise value type available:
  `APP_SETTINGS_KEY: Final = web.AppKey("APP_SETTINGS_KEY", ApplicationSettings)`.
- Follow the containing module's middleware, routing, and exception-handling
  patterns; use `web.RouteTableDef()` where that is the local route convention.
