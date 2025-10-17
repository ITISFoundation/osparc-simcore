---
applyTo: '**/*.py'
---

## 🛠️Coding Instructions for Python in This Repository

Follow these rules **strictly** when generating Python code:


### Python Version

* Use Python 3.11: Ensure all code uses features and syntax compatible with Python 3.11.

### General Coding Practices & Formatting

* Follow [Python Coding Conventions](../../docs/coding-conventions.md) **strictly**.
* Format code with `black` and `ruff`.
* Lint code with `ruff` and `pylint`.
* Place **all imports at the top** of the file.
* Use `f-string` formatting for all string interpolation except for logging message strings.
* Use **relative imports** within the same package/module.
  - For imports within the same repository/project, always use relative imports (e.g., `from ..constants import APP_SETTINGS_KEY` instead of `from simcore_service_webserver.constants import APP_SETTINGS_KEY`)
  - Use absolute imports only for external packages AND main.py-like modules used in entrypoints


### Documentation Guidelines (docstrings)

```python
# ✅ DO THIS
async def fetch_data(user_id: UUID) -> Data:
    """Raises:
        NotFoundError: If user doesn't exist"""

def process_items(items: Sequence[Item]) -> Result:
    """Complex reordering using Knuth's algorithm

    Raises:
        ValueError: If items contains duplicates"""

# ❌ NOT THIS
def add(a: int, b: int):
    """Adds two numbers"""  # Redundant
```

**Rules:**
1. Clear names + type hints first
2. Document exceptions (always)
3. Document complex logic or rationale only if not clear from context
4. Skip obvious behavior. Prefer no docstring if nothing above applies


### Type Annotations

* Always use full type annotations for all functions and class attributes.
* ❗ **Exception**: Do **not** add return type annotations in `test_*` functions.


### Library Compatibility

Ensure compatibility with the following library versions:

* `sqlalchemy` ≥ 2.x
* `pydantic` ≥ 2.x
* `fastapi` ≥ 0.100


### JSON Serialization

* Prefer `json_dumps` / `json_loads` from `common_library.json_serialization` instead of the built-in `json.dumps` / `json.loads`.
* When using Pydantic models, prefer methods like `model.model_dump_json()` for serialization.

### aiohttp Framework

* **Application Keys**: Always use `web.AppKey` for type-safe application storage instead of string keys
  - Define keys with specific types: `APP_MY_KEY: Final = web.AppKey("APP_MY_KEY", MySpecificType)`
  - Use precise types instead of generic `object` when the actual type is known
  - Example: `APP_SETTINGS_KEY: Final = web.AppKey("APP_SETTINGS_KEY", ApplicationSettings)`
  - Store and retrieve: `app[APP_MY_KEY] = value` and `data = app[APP_MY_KEY]`
* **Request Keys**: Use `web.AppKey` for request storage as well for consistency and type safety
* **Middleware**: Follow the repository's middleware patterns for cross-cutting concerns
* **Error Handling**: Use the established exception handling decorators and patterns
* **Route Definitions**: Use `web.RouteTableDef()` and organize routes logically within modules

### Running tests
* Use `--keep-docker-up` flag when testing to keep docker containers up between sessions.
* Always activate the python virtual environment before running pytest.
