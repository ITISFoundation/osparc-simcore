---
applyTo: '**/requirements/**'
---

# Requirements file conventions

These rules apply to `*.in` and `*.txt` files in any `requirements/` directory.
Follow the workflow in
[`requirements/python-dependencies.md`](../../requirements/python-dependencies.md).

- Sort `*.in` entries by package name within each existing group of
  `--constraint` lines, intra-repo packages, or third-party packages. Ignore case, version
  specifiers, and extras when sorting. Treat `-` and `_` as equivalent.
  Keep the group order and place constraints before requirements. Keep lines
  starting with `--` in the first group.
- Identify generated `*.txt` files by their generation header, matching `*.in`
  input, or documented role. Edit the input and run `make reqs` using the linked
  workflow. For example, edit `_base.in` to regenerate `_base.txt`.
  Never edit generated files by hand.
- A missing matching `*.in` is not necessarily an error. You may edit
  hand-maintained constraints, tooling requirements, and installation shortcuts
  directly. Examples include `constraints.txt`, `devenv.txt`, and `ci.txt`.
  If a file's role is unclear, check its header and the owning project's
  workflow before editing.
- If `make reqs` fails or does not exist, stop, report the error output, and do
  not edit generated files by hand as a fallback.
