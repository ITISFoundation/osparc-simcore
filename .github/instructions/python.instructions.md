---
applyTo: '**/*.py'
---
Provide project context and coding guidelines that AI should follow when generating code, answering questions, or reviewing changes.

## 🛠️Coding Instructions for Python in This Repository

Follow these rules **strictly** when generating Python code:

### 1. Python Version

* Use Python 3.13: Ensure all code uses features and syntax compatible with Python 3.13.

### 2. **Type Annotations**

* Always use full type annotations for all functions and class attributes.
* ❗ **Exception**: Do **not** add return type annotations in `test_*` functions.

### 3. **Code Style & Formatting**

* Follow [Python Coding Conventions](../../docs/coding-conventions.md) **strictly**.
* Format code with `black` and `ruff`.
* Lint code with `ruff` and `pylint`.

### 4. **Library Compatibility**

Ensure compatibility with the following library versions:

* `sqlalchemy` ≥ 2.x
* `pydantic` ≥ 2.x
* `fastapi` ≥ 0.100


### 5. **Code Practices**

* Use `f-string` formatting for all string interpolation except for logging message strings.
* Use **relative imports** within the same package/module.
  - For imports within the same repository/project, always use relative imports (e.g., `from ..constants import APP_SETTINGS_KEY` instead of `from simcore_service_webserver.constants import APP_SETTINGS_KEY`)
  - Use absolute imports only for external libraries and packages
* Place **all imports at the top** of the file.
* Document functions when the code is not self-explanatory or if asked explicitly.


### 6. **JSON Serialization**

* Prefer `json_dumps` / `json_loads` from `common_library.json_serialization` instead of the built-in `json.dumps` / `json.loads`.
* When using Pydantic models, prefer methods like `model.model_dump_json()` for serialization.

### 7. **aiohttp Framework**

* **Application Keys**: Always use `web.AppKey` for type-safe application storage instead of string keys
  - Define keys with specific types: `APP_MY_KEY: Final = web.AppKey("APP_MY_KEY", MySpecificType)`
  - Use precise types instead of generic `object` when the actual type is known
  - Example: `APP_SETTINGS_KEY: Final = web.AppKey("APP_SETTINGS_KEY", ApplicationSettings)`
  - Store and retrieve: `app[APP_MY_KEY] = value` and `data = app[APP_MY_KEY]`
* **Request Keys**: Use `web.AppKey` for request storage as well for consistency and type safety
* **Middleware**: Follow the repository's middleware patterns for cross-cutting concerns
* **Error Handling**: Use the established exception handling decorators and patterns
* **Route Definitions**: Use `web.RouteTableDef()` and organize routes logically within modules

### 8. **Running tests**
* Use `--keep-docker-up` flag when testing to keep docker containers up between sessions.
* Always activate the python virtual environment before running pytest.
