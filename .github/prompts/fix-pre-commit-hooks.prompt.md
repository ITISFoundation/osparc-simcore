---
agent: agent
description: Automatically fixes all issues reported by pre-commit hooks on the selected files.
model: GPT-4.1
---

Run all pre-commit hooks (from the Python virtual environment) **only on the files that are added as context**. Fix every issue reported by the hooks in those files only. Repeat until no issues remain.

### Python Virtual Environment
- Location: `osparc-simcore/.venv`
- Activate: `source .venv/bin/activate`
