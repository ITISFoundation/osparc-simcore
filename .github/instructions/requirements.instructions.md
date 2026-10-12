---
applyTo: '**/requirements/**'
---

# Requirements file conventions

Applies to `*.in` and `*.txt` files in any `requirements/` directory. Workflow:
[`requirements/python-dependencies.md`](../../requirements/python-dependencies.md).

- Keep `*.in` entries sorted case-insensitively by package name, ignoring
  version specifiers and extras, with `-` and `_` treated as equivalent, within
  each existing group (`--constraint` lines, intra-repo packages, third-party).
  Keep the group order, and keep constraints before requirements. Lines starting
  with `--` keep their position as the first group.
- Identify generated `*.txt` files by their generation header, matching `*.in`
  input, or documented role. Edit the input (for example, `_base.in` for
  `_base.txt`) and run `make reqs` using the linked workflow; never edit
  generated files by hand.
- A missing matching `*.in` does not imply an error: hand-maintained constraints,
  tooling requirements, and installation shortcuts (such as `constraints.txt`,
  `devenv.txt`, and `ci.txt`) may be edited directly. If a file's role is unclear,
  check its header and the owning project's workflow before editing.
- If `make reqs` fails or does not exist, stop, report the error output, and do
  not edit generated files by hand as a fallback.
