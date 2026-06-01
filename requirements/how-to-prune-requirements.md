
# How to prune unused requirements

Over time a library accumulates dependencies that are no longer imported but
remain listed in its `_base.in`. These steps remove them from a library and
propagate the cleanup downstream. The example uses `simcore-sdk`; it is
analogous for any package.

## 1. Prune the library itself

Detect which dependencies are actually imported with
[pipreqs](https://github.com/bndr/pipreqs), then prune `_base.in` accordingly:

```bash
pip install pipreqs
pipreqs packages/simcore-sdk/src/simcore_sdk     # produces requirements.txt
```

- Compare the generated list against `packages/simcore-sdk/requirements/_base.in`
  and remove libraries no longer imported.
- Review intra-repo dependencies (other `packages/*`) manually — pipreqs does
  not detect those reliably.
- Recompile: `make touch reqs`.

## 2. Propagate downstream (without bumping unrelated deps)

Find which services/libraries depend on the pruned library:

```bash
grep --include=\*.in -rnw -e 'packages/simcore-sdk/requirements/_base.in' .
```

In each dependent's `requirements/` folder, **selectively** upgrade only the
libraries that `simcore-sdk` pulls in (e.g. `aiohttp`):

```bash
make touch
make reqs upgrade=aiohttp
```

Verify the resulting diff in `requirements/` contains only the intended partial
upgrade.

## See also

- [python-dependencies.md](python-dependencies.md) — overall dependency model and security workflow
- [how-to-unify-versions.md](how-to-unify-versions.md)
- [how-to-upgrade-python.md](how-to-upgrade-python.md)
