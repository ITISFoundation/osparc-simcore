# Setps to upgrade python

This is a guideline for repo-wide upgrade of python. Here we assume we are moving from an *current* version ``py3.X`` to a newer version ``py3.Y``


- [ ] Open an issue and paste the following steps (exemple https://github.com/ITISFoundation/osparc-issues/issues/877)
- [ ] Upgrade tests & tools requirements (in `py3.X`)
- [ ] Upgrade primary libraries (e.g. fastapi, etc)  (in `py3.X`)
- [ ] Upgrade ``pip`` (in `py3.X`)
- [ ] Check compatibility and bugs sections in [requirements/constraints.txt](../requirements/constraints.txt)
- [ ] Prune unused libraries repo-wide see [how-to-prune-requirements.md](../requirements/how-to-prune-requirements.md)  (in `py3.X`)
- [ ] Unify versions repo wide when possible. See [how-to-unify-versions.md](../requirements/how-to-unify-versions.md)
- [ ] Upgrade to `py3.Y`
   - read [requirements/how-to-upgrade-python.md](../requirements/how-to-upgrade-python.md)
   - read release notes to check for warnings/recommendations for the upgrade
- [ ] Run repo-wide pip-tools with new python version (all ``requirements.txt`` should at least change doc  headers)
- [ ] Check deprecation warnings both in code and libraries
- [ ] Remove backport libraries. See [/requirements/packages-notes.md](../requirements/packages-notes.md)
   - https://github.com/ITISFoundation/osparc-simcore/pull/4047
- [ ] Remove ``pylint`` `py3.X` github action and add new step to pylint against next version of `py3.Y` (if any)
- [ ] Update ``pyupgrade`` config in ``pre-commit-config.yaml``:  e.g. ``--py3Y-plus``
- [ ] Is there something we can automate better? Do it now or open an issue
- [ ] Is there something we can document better? Do it!
