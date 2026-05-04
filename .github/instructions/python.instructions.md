---
applyTo: '**/*.py'
---

## 🛠️Coding Instructions for Python in This Repository

Follow these rules **strictly** when generating Python code:

### Python Version

* Use Python 3.13: Ensure all code uses features and syntax compatible with Python 3.13.

### Type Annotations

* Always use full type annotations for all functions and class attributes.
* ❗ **Exception**: Do **not** add return type annotations in `test_*` functions.

### Documentation with Annotated Types

* Use `annotated_types.doc()` for parameter and return type documentation instead of traditional docstring Args/Returns sections
* **Apply documentation only for non-obvious parameters/returns**:
  - Document complex behaviors that can't be deduced from parameter name and type
  - Document validation rules, side effects, or special handling
  - Skip documentation for self-explanatory parameters (e.g., `engine: AsyncEngine`, `product_name: ProductName`)
* **Import**: Always add `from annotated_types import doc` when using documentation annotations

**Examples:**
```python
from typing import Annotated
from annotated_types import doc

async def process_users(
    engine: AsyncEngine,  # No doc needed - self-explanatory
    filter_statuses: Annotated[
        list[Status] | None,
        doc("Only returns users with these statuses")
    ] = None,
    limit: int = 50,  # No doc needed - obvious
) -> Annotated[
    tuple[list[dict], int],
    doc("(user records, total count)")
]:
    """Process users with filtering.

    Raises:
        ValueError: If no filters provided
    """
```

* **Docstring conventions**:
  - Keep docstrings **concise**, focusing on overall function purpose
  - Include `Raises:` section for exceptions
  - Avoid repeating information already captured in type annotations
  - Most information should be deducible from function name, parameter names, types, and annotations

### Code Style & Formatting

* Follow [Python Coding Conventions](../../docs/coding-conventions.md) **strictly**.
* Format code with `ruff`.
* Lint code with `ruff` and `pylint`.

### Library Compatibility

Ensure compatibility with the following library versions:

* `sqlalchemy` ≥ 2.x
* `pydantic` ≥ 2.x
* `fastapi` ≥ 0.100

### Code Practices

* Use `f-string` formatting for all string interpolation except for logging message strings.
* Use **relative imports** within the same package/module.
  - For imports within the same repository/project, always use relative imports (e.g., `from ..constants import APP_SETTINGS_KEY` instead of `from simcore_service_webserver.constants import APP_SETTINGS_KEY`)
  - Use absolute imports only for external libraries and packages
* Place **all imports at the top** of the file.
* Document functions when the code is not self-explanatory or if asked explicitly.

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
