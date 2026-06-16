# How to unify package versions across the repo

The same package listed in different `requirements/` files should resolve to as
similar a version as possible throughout the repository. Different versions of
the same package across files is called *dispersion* and should be minimized.

## 1. Generate the dispersion report

```bash
make devenv
source .venv/bin/activate
cd requirements/tools
make report          # writes and prints report.ignore.md
```

The report's **Repo-wide overview of libraries** table lists each package with
its versions in the `versions-base`, `versions-test` and `versions-tool`
columns. Targets for unification are packages showing **more than one version**
in any column, in particular:

- multiple versions in `versions-base` (and none in `versions-test`)
- multiple versions in `versions-test` (and none in `versions-base`)

## 2. Unify, one package at a time

Upgrade each target package repo-wide and commit separately so any regression
can be traced to a single library bump:

```bash
packages=<pkgA>,<pkgB>,<pkgC>   # from the report

for u in ${packages//,/ }; do
   make reqs-all upgrade=$u &> reqs-$u.log
   git commit -am "upgrades $u" --no-verify
done
```

> `uv pip compile` also accepts `--upgrade X --upgrade Y` to bump several at
> once, but we prefer one-by-one commits for traceability.

## See also

- [python-dependencies.md](python-dependencies.md) — overall dependency model and security workflow
- [how-to-prune-requirements.md](how-to-prune-requirements.md)
- [how-to-upgrade-python.md](how-to-upgrade-python.md)
