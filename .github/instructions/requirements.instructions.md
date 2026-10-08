---
applyTo: '**/requirements/**'
---

# Requirements file conventions

Applies to `*.in` and `*.txt` files in any `requirements/` directory. Workflow:
[`requirements/python-dependencies.md`](../../requirements/python-dependencies.md).

- Keep `*.in` entries alphabetical within each existing group (`--constraint`
  lines, intra-repo packages, third-party). Keep the group order, and keep
  constraints before requirements.
- Treat `*.txt` files as generated: edit the matching `*.in` and run
  `make reqs`; never edit `*.txt` by hand.
