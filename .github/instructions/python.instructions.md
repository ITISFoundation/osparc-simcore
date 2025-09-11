---
applyTo: '**/*.py'
---
Provide project context and coding guidelines that AI should follow when generating code, answering questions, or reviewing changes.

## 🛠️Coding Instructions for Python in This Repository

Follow these rules **strictly** when generating Python code:

### 1. Python Version

* Use Python 3.11: Ensure all code uses features and syntax compatible with Python 3.11.

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
* Place **all imports at the top** of the file.
* Document functions when the code is not self-explanatory or if asked explicitly.


### 6. **JSON Serialization**

* Prefer `json_dumps` / `json_loads` from `common_library.json_serialization` instead of the built-in `json.dumps` / `json.loads`.
* When using Pydantic models, prefer methods like `model.model_dump_json()` for serialization.
