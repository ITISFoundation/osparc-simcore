---
name: fix-pre-commit-hooks
description: Automatically fixes all issues reported by pre-commit hooks on the selected files.
disable-model-invocation: true
---

<!-- markdownlint-disable -->
<!-- model-facing instructions; repo-wide markdownlint rollout deferred -->
Run all pre-commit hooks (`pre-commit` is installed as a uv tool by `make devenv`) **only on the files that are added as context**. Fix every issue reported by the hooks in those files only. Repeat until no issues remain.

### Python Virtual Environment
- Location: `osparc-simcore/.venv`
- Activate: `source .venv/bin/activate`
