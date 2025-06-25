# GitHub Copilot Instructions

This document provides guidelines and best practices for using GitHub Copilot in the `osparc-simcore` repository and other Python and Node.js projects.

## General Guidelines

1. **Test-Driven Development**: Write unit tests for all new functions and features. Use `pytest` for Python and appropriate testing frameworks for Node.js.
2. **Environment Variables**: Use [Environment Variables Guide](../docs/env-vars.md) for configuration. Avoid hardcoding sensitive information.
3. **Documentation**: Prefer self-explanatory code; add documentation only if explicitly requested by the developer.

---

## 🛠️Coding Instructions for Python in This Repository

Follow these rules strictly when generating Python code:

### 1. Python Version

* Use Python 3.11: Ensure all code uses features and syntax compatible with Python 3.11.

### 2. **Type Annotations**

* Always use full type annotations for all functions and class attributes.
* ❗ **Exception**: Do **not** add return type annotations in `test_*` functions.

### 3. **Code Style & Formatting**

* Follow [Python Coding Conventions](../docs/coding-conventions.md) **strictly**.
* Format code with `black`.
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
* Add comments **only when the code is not self-explanatory**.


### 6. **JSON Serialization**

* Prefer `json_dumps` / `json_loads` from `common_library.json_serialization` instead of the built-in `json.dumps` / `json.loads`.
* When using Pydantic models, prefer methods like `model.model_dump_json()` for serialization.

---

## 🛠️Coding Instructions for Node.js in This Repository

* Use ES6+ syntax and features.
* Follow the `package.json` configuration for dependencies and scripts.
* Use `eslint` for linting and `prettier` for code formatting.
* Write modular and reusable code, adhering to the project's structure.
