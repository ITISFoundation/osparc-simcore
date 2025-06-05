# GitHub Copilot Instructions

This document provides guidelines and best practices for using GitHub Copilot in the `osparc-simcore` repository and other Python and Node.js projects.

## General Guidelines

1. **Use Python 3.11**: Ensure that all Python-related suggestions align with Python 3.11 features and syntax.
2. **Node.js Compatibility**: For Node.js projects, ensure compatibility with the version specified in the project (e.g., Node.js 14 or later).
3. **Follow Coding Conventions**: Adhere to the coding conventions outlined in the `docs/coding-conventions.md` file.
4. **Test-Driven Development**: Write unit tests for all new functions and features. Use `pytest` for Python and appropriate testing frameworks for Node.js.
5. **Environment Variables**: Use environment variables as specified in `docs/env-vars.md` for configuration. Avoid hardcoding sensitive information.
6. **Documentation**: Prefer self-explanatory code; add documentation only if explicitly requested by the developer.

## Python-Specific Instructions

- Always use type hints and annotations to improve code clarity and compatibility with tools like `mypy`.
  - An exception to that rule is in `test_*` functions return type hint must not be added
- Follow the dependency management practices outlined in `requirements/`.
- Use `ruff` for code formatting and for linting.
- Use `black` for code formatting and `pylint` for linting.
- ensure we use `sqlalchemy` >2 compatible code.
- ensure we use `pydantic` >2 compatible code.
- ensure we use `fastapi` >0.100 compatible code
- use f-string formatting
- Only add comments in function if strictly necessary
- use relative imports
- imports should be at top of the file


### Json serialization

- Generally use `json_dumps`/`json_loads` from `common_library.json_serialization` to built-in `json.dumps` / `json.loads`.
- Prefer Pydantic model methods (e.g., `model.model_dump_json()`) for serialization.


## Node.js-Specific Instructions

- Use ES6+ syntax and features.
- Follow the `package.json` configuration for dependencies and scripts.
- Use `eslint` for linting and `prettier` for code formatting.
- Write modular and reusable code, adhering to the project's structure.

## Copilot Usage Tips

1. **Be Specific**: Provide clear and detailed prompts to Copilot for better suggestions.
2. **Iterate**: Review and refine Copilot's suggestions to ensure they meet project standards.
3. **Split Tasks**: Break down complex tasks into smaller, manageable parts for better suggestions.
4. **Test Suggestions**: Always test Copilot-generated code to ensure it works as expected.

## Additional Resources

- [Python Coding Conventions](../docs/coding-conventions.md)
- [Environment Variables Guide](../docs/env-vars.md)
- [Steps to Upgrade Python](../docs/steps-to-upgrade-python.md)
- [Pydantic Annotated fields](../docs/llm-prompts/pydantic-annotated-fields.md)
