---
applyTo: '**/requirements/**'
---

# Requirements file conventions

Applies to pip-tools input and output files (`*.in`, `*.txt`) in any
`requirements/` directory. Central workflow and scripts:
[`requirements/Makefile`](../../requirements/Makefile) and
[`requirements/python-dependencies.md`](../../requirements/python-dependencies.md).

## Ordering

- Keep hand-maintained entries in a `*.in` file alphabetically sorted when
  order carries no meaning: requirement lines, and `--requirement` /
  `--constraint` references (sorted by path).
- Group entries by purpose when the file already does (e.g. `--constraint`
  lines, intra-repo package references, third-party requirements) and keep the
  existing section order. Alphabetize within a group only.
- Preserve ordering that carries meaning, such as constraint-before-requirement
  precedence. Do not reorder across sections as cleanup.

## Generated files

- Treat `*.txt` files as generated artifacts of `uv pip compile`; change them
  by editing the matching `*.in` file and re-running the repository workflow
  (`make reqs`), not by hand and not with `pip-compile`.
