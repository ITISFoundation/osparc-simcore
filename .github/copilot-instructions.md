# Copilot Instructions for osparc-simcore

## Coding conventions

- See `.github/instructions/` for language- and domain-specific rules (`python.instructions.md`, `node.instructions.md`).
- In the `../docs/` folder, find architecture and design docs for backend services, computational pipelines, and testing workflows.
- Use `pytest` for Python tests; follow test-driven development.
- Use the [Environment Variables Guide](../docs/env-vars.md) for configuration — never hardcode secrets.
- Prefer self-explanatory code over comments; add docs only when explicitly requested.

## Testing workflows

For detailed instructions on running unit tests, integration tests, building Docker images, Docker cleanup, and known issues, see [`AGENTS.md`](../AGENTS.md) in the repo root.
