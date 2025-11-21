---
mode: edit
description: Converts string-based aiohttp app key constants to type-safe web.AppKey
model: GPT-4.1
---

Convert all string-based app key constants to use type-safe web.AppKey.

- Replace patterns like:
  ```python
  CONSTNAME_APPKEY: Final[str] = f"{__name__}.my_key"
  ```
  with:
  ```python
  from aiohttp import web
  CONSTNAME_APPKEY: Final = web.AppKey("CONSTNAME", ValueType)
  ```
  (Replace ValueType with the actual type stored under this key.)

- Update all usages:
  - `app[CONSTNAME_APPKEY] = value`
  - `data = app[CONSTNAME_APPKEY]` or `data = request.app[CONSTNAME_APPKEY]`

- Key constant MUST be UPPERCASE
- Key name MUST be suffixed `_APPKEY`
- Remove any f"{__name__}..." patterns; use a simple string identifier in web.AppKey.
- Ensure all keys are type-safe and self-documenting.
- IF you change the original name, you MUST change all the references
