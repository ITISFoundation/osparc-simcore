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
- Treat `*.txt` files as generated: edit the `*.in` file with the same base name
  in the same directory (for example, `requirements/dev.in` generates
  `requirements/dev.txt`) and run `make reqs`; never edit `*.txt` by hand.
- If no matching `*.in` file exists for a `*.txt` file, do not create or edit
  the `*.txt` file. Report the mismatch to the user instead.
- If `make reqs` fails or does not exist, stop, report the error output, and do
  not edit `*.txt` files by hand as a fallback.
