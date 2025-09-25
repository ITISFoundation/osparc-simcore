---
mode: edit
model: GPT-4.1
---

Convert all string-based app key constants to use type-safe web.AppKey.

- Replace patterns like:
  ```python
  MY_APPKEY: Final[str] = f"{__name__}.my_key"
  ```
  with:
  ```python
  from aiohttp import web
  MY_APPKEY: Final = web.AppKey("MY_APPKEY", MySpecificType)
  ```
  (Replace MySpecificType with the actual type stored under this key.)

- Update all usages:
  - `app[MY_APPKEY] = value`
  - `data = app[MY_APPKEY]` or `data = request.app[MY_APPKEY]`

- Key constant MUST be UPPERCASE
- Key name MUST be suffixed `_APPKEY`
- Remove any f"{__name__}..." patterns; use a simple string identifier in web.AppKey.
- Ensure all keys are type-safe and self-documenting.
- IF you change the original name, you MUST change all the references
