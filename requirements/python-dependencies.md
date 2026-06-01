# Management of python dependencies

Since [issue 234](https://github.com/ITISFoundation/osparc-simcore/issues/234) the dependencies management for python packages (i.e. setup of installation requirements) has been redesigned and normalized.


## Motivation

Managing the dependency across multiple packages can be truly daunting and error-prone.

<!--
TODO: finish!
- As a developer, I just want to add a list of requirements on the go
- Each package in the requirements have its own requirements specifications and so on.
- Listing up all these dependency constraints should result in final explicit list of requirements
- Each package adds some version constraints to its dependencies.
  - The management system shall be able to find a list of all packages needed and the versions that satisfy *all constraints* in place
- The dependencies have to be kept up-to-date regularly (e.g. due to security patches;  new feature in our package might add new direct dependencies to our requirements)
- Inter-dependent libraries typically have different release cycles creating in time version conflicts (e.g. package A and B strictly depend on different versions of C)


- packages uses input requirements as install-requirements (i.e. entry in setup and in requirements/ci.txt) NOT compiled ones
- services use compiled requirements



- tests packages with the latest (i.e. compile requirements to latest version)
  - if tests fails, then add constraints in input requirements
    - try adding tests that check inter-library compatibility
  - if tests succeed, you can use them in services
  - if at least one service has a problem, we need to decide whether to add a constraint:
    a) at the package level => will ensure is tested but is constraining all services
    b) at the service level => only affects service but cannot do isolate tests against latest upgrades


### How to purge unused requirements?


### Propagation of constraints

- Situation:  upgrading one package the developer finds an issue, e.g.
```
coverage==5.0.3 # TODO: Downgraded because of a bug https://github.com/nedbat/coveragepy/issues/716

pytest~=5.3.5  # Bug in pytest-sugar https://github.com/Teemu/pytest-sugar/issues/187
pytest-aiohttp  # incompatible with pytest-asyncio. See https://github.com/pytest-dev/pytest-asyncio/issues/76
```
- Question: how to make sure this is also taken into account in other places?


!-->

## Rationale

Every python package specifies its dependencies to the installer via the ``setup.py``. Typically, dependencies to third-party libraries are listed in a text file denoted as the *requirements* file. Notice that the requirements must be in sync with the ``install_requires`` entry in the ``setup.py`` (see [Setup vs requirements]).

- All dependency specifications are under ``requirements`` folder
- There are two type of files there with extensions ``*.in`` and ``*.txt``
- All ``*.in`` files contain third-party dependencies
  - created by the developer
  - should not be very restrictive with versions. Add only constraints that must be enforced: e.g. to fix vulnerabilities, compatibility issues, etc
  - used as input to [uv] which will determine the final version used
- All ``*.txt`` files are actual requirements, i.e. can be used in ``uv pip install -r requirements/filename.txt``. There are two types:
  1. *frozen dependencies* are automatically created using [uv] from ``_*.in`` files. These includes a strict list of libraries with pinned versions. Every ``_*.in`` file has a ``_*.txt`` counterpart. **Notice** that these files start with ``_`` and therefore are listed at the top of the tree. These follow a [workflow of layered requirements](https://github.com/jazzband/pip-tools#workflow-for-layered-requirements) in which ``_base.txt`` contains dependencies for production and ``_test.txt`` **extra** dependencies for setting up testing.
  2. installation *shortcuts* for three different *contexts*:
     1. **development**: ``uv pip install -r requirements/dev.txt``
        - Installs target package in [develop (or edit)](https://pip.pypa.io/en/stable/reference/pip_install/#usage) mode as well as  other tools or packages within the simcore repository
     2. **contiguous integration**: ``uv pip install -r requirements/ci.txt``
        - Installs target package, simcore-repo  and tests dependencies
     3. **production**: ``uv pip install -r requirements/prod.txt``
        - Installs target package  and simcore-repo dependencies
- ``setup.py`` read dependencies into the setup (a bit more below)
  - **libraries** (e.g. in [packages/service-lib](../packages/service-library/setup.py)) have *flexible dependencies*, i.e. requirements read from  ``requirements/_base.in``
  - **services** (e.g. in [services/web/server](../services/web/server/setup.py) ) have *strict dependencies* and therefore it reads from ``requirements/_base.txt`` where all versions are pinned.


### Weak *vs* strong requirements & libraries *vs* services requirements

Every package's ``setup.py`` defines the [dependency management](https://setuptools.pypa.io/en/latest/userguide/dependency_management.html#dependencies-management-in-setuptools) under different scenarios, namely ``install_require``,
``tests_require``, ``extras_require`` and ``setup_require``.


The files under ``requirements`` and have ``*.in`` or ``*.txt`` extensions to separate input requirements (w/o many constraints) from frozen requirements (every library is constrained to a pinned version). Depending on whether we are setting up a library or a service, different listing apply.

Basically, the idea is that *libraries* shall have *weak* constraint requirements while *services* shall have *hard* constraints requirements.  Weak requirements are in the ``*.in`` files while *hard* are in the ``*.txt`` files.

The main reason is that the former are shared among different services and provides more degrees of freedom. In the case of the services, those are final and there is no need for those degrees of freedom.

Libraries requirements are only frozen for testing (therefore ``tests_require= .. txt`` in libraries setup).


 ---
## Limitations

1. ~~Needs to install [pip-tools]~~ **RESOLVED [June 2026]**: replaced by [uv]; the `make reqs` recipes run `uv pip compile` in an isolated tooling image, no longer polluting the venv.
   - ~~pollutes the venv~~
   - ~~**SOLUTION** under development: [pip-kit](https://github.com/ITISFoundation/dockerfiles/tree/master/pip-kit) is a containarized solution with multiple packages~~
1. Requirements from in-place packages are not accounted in services upon *pip-compilation* since they cannot be added to ``_base.txt`` or ``_test.txt`` !!!!!!
1. Adding dependencies to **in-place simcore's repo packages** is error-prone since it requires changes in multiple places, namely:
   - paths entries in ``requirements/[dev|ci|prod].txt``
   - package names+version in requirements list for ``setup.py``
1. ~~Cannot use [pip-tools] (e.g. ``pip-sync``) with ``requirements/ci.txt`` or ``requirements/prod.txt`` because of in-place dependencies: ``pip-compile does not support URLs as packages, unless they are editable. Perhaps add -e option? (constraint was: file:///home/crespo/devp/osparc-simcore/packages/s3wrapper (from -r requirements/ci.txt (line 13)))``~~ **RESOLVED [June 2026]**: [uv] resolves local path dependencies natively.


### Updates [March 2020]

1. Created common makefile in [requirements/base.Makefile](requirements/base.Makefile)

### Updates [June 2026]

1. Replaced [pip-tools] with [uv] for all `pip-compile` operations. The Makefile targets (`make reqs`, `make reqs-all`) call `uv pip compile` internally — developer-facing commands are unchanged.
2. Added `requirements/constraints.txt` as a **repo-wide constraint file** applied to every `*.in` compilation via `--constraint ../../../../requirements/constraints.txt`. This is the primary mechanism for CVE fixes and strategic version pins (see Security workflow below).
3. Added automated CVE scanning via `pip-audit` (see `.github/workflows/pip-audit.yml`).
4. Disabled Dependabot pip version-update PRs; Docker and GitHub Actions ecosystems are tracked with a cool-down policy (see `.github/dependabot.yml`).

## Workflows

To install a given workflow we use directly [pip]. Assume we are in the package folder

```console
$ cd path/to/package
```
then to **develop** your library/service type
```console
$ uv pip install -r requirements/dev.txt
```
for **CI** of your your library/service (normally used in ci/travis/...) type
```console
$ uv pip install -r requirements/ci.txt
```
to **deploy** your service
```console
$ uv pip install -r requirements/prod.txt
```
or if it is a library, then ``uv pip install .`` is preferred.


### Updating dependencies

This is the typical [uv] workflow

1. developer **only** sets ``*.in`` files (or the shortcut files)
2. ``uv pip compile`` requirements (via ``make reqs`` in the package folder)
3. ``uv pip install -r requirements/[dev|ci|prod].txt`` depending on your context


### auto-compile requirements

Or how to convert all ``requirements/*.in`` into ``requirements/*.txt`` using the Makefile:

```console
$ cd path/to/package/requirements
$ make help
all – compiles all requirements/*.in -> requirements/*.txt (via uv pip compile)
clean – Cleans all requirements/*.txt (except dev.txt, ci.txt, prod.txt, dev.txt)
help – Display all callable targets
$ make
```

The Makefile targets call ``uv pip compile`` internally in an isolated tooling environment.

### Updating testing & tooling requirements (t&t reqs)

For packages, is easily automated since ALL requirements in packages
are frozen to define a repeatable testing. Notice that the requirements
in the setup they are fed from .in requirements files and not the .txt
requirements. For that reason, a full upgrade of requirements in every
package will ONLY affect testing and tooling of the package. In short,
to upgrade t&t reqs in packages, we must:
- touch ``*.in``
- ``make reqs``
and should change ``_base.txt, _test.txt, _tool.txt``


In the case of services is a bit more involved since
we must compile ``_test.*`` and ``_tool.*`` without changing ``_base.*``
- touch ``_test.*, _tool.*``
- ``make reqs``
BUT the problem is that ``_base.in`` includes dependencies to packages
``*.in`` files which MIGHT have added NEW CONSTRAINTS. For that reason,
we need to update carefully ``_base.*`` as well such that it produces
a new ``_base.txt`` that accounts for ONLY the CONSTRAINTS. A trick
is to call ``make reqs upgrade=<some-fixed-version-dependency-already-in-base-txt>``. The latter
will upgrade only packages that do not suit the constraints.

So, this is a typical workflow:

```console
$ cd requirements/tools
$ make build-nc
$ make shell
(container)~$ cd requirements/tools
(container)~$ cd make reqs
```

```console
$ cd requirements/tools
$ make build-nc
$ make shell
crespo@8ac9edf78469:~$ cd services/api-server/requirements
```
#### upgrades _base.in ONLY on constraints (e.g. fix upgrade to a given version)
```console
crespo@8ac9edf78469:~/services/api-server/requirements$ touch _base.in
crespo@8ac9edf78469:~/services/api-server/requirements$ make reqs upgrade=fastapi==x.x
```
#### full upgrade of tests
```console
crespo@8ac9edf78469:~/services/api-server/requirements$ touch _tests.in
crespo@8ac9edf78469:~/services/api-server/requirements$ make reqs
```
---
## Security workflow

### Why Dependabot pip is disabled

Dependabot's `package-ecosystem: pip` works by editing `*.txt` files directly. In this repo `*.txt` files are **generated artifacts** — they are compiled from `*.in` sources by `uv pip compile` and must respect the full constraint chain:

```
_base.in  →  _base.txt  →  _test.in  →  _test.txt
              ↑
       requirements/constraints.txt  (applied to every compile)
```

If Dependabot edits `_base.txt` directly, the change is invisible to `uv pip compile` and will be overwritten the next time `make reqs` runs. Dependabot pip version-update PRs are therefore set to `open-pull-requests-limit: 0` (disabled). GitHub's security-alert mechanism uses a separate internal limit and is **not** affected by this setting.

### `requirements/constraints.txt` — the security override layer

This file is applied as `--constraint` to **every** `*.in` compilation across the repo. It is the canonical place to:

- Pin a minimum safe version after a CVE (e.g. `aiohttp>=3.11.14  # CVE-2024-23334`).
- Block a broken release across all services at once (e.g. `httpx!=0.28.0`).
- Coordinate a strategic upgrade that spans multiple services.

Do **not** use service-local `*.in` files for these cross-cutting pins — they would silently miss other services.

### Automated CVE scanning — pip-audit

The workflow [`.github/workflows/pip-audit.yml`](../.github/workflows/pip-audit.yml) runs:

- **Weekly** (Monday 06:00 UTC) and on any push/PR touching `**/requirements/*.{in,txt}` or `requirements/constraints.txt`.
- Scans all `_base.txt` files (35 files across 18 services + 9 packages): **CI fails** on any CVE.
- Scans all `_test.txt` files: **warning only**, never blocks CI.
- Uploads a SARIF report to the GitHub Security tab and writes a markdown summary in the job log.

Security SLA:

| Severity     | Deadline                  |
| ------------ | ------------------------- |
| Critical     | 24 hours                  |
| High         | 1 week                    |
| Medium / Low | next regular update cycle |

### Applying a security fix

When a CVE is found in a production dependency:

1. Check the fix version on PyPI / the CVE advisory.
2. Run the propagation script:
   ```console
   $ scripts/propagate-security-fix.sh <package> <constraint> [<CVE-id>]
   # Example:
   $ scripts/propagate-security-fix.sh aiohttp ">=3.11.14" CVE-2024-23334
   ```
   The script:
   - Adds or updates the pin in `requirements/constraints.txt`.
   - Runs `make -C requirements/tools reqs-all upgrade=<package>` which re-pins the package across all `*.txt` files in the repo.
   - Prints the changed files and a ready-made `git commit` command.
3. Review the diff (`git diff requirements/`), run unit tests, then commit.

For an isolated single-service fix use `make reqs upgrade=<package>` inside that service's `requirements/` folder instead of `reqs-all`.

### Cool-down / N-1 policy

A *cool-down* (also called patch-lag or N-1 policy) delays adoption of newly released versions to avoid inheriting bugs introduced in fresh releases.

| Dependency type         | Major  | Minor  | Patch  | Security  |
| ----------------------- | ------ | ------ | ------ | --------- |
| GitHub Actions          | 30 d   | 14 d   | 7 d    | immediate |
| Docker base images      | 30 d   | 14 d   | 7 d    | immediate |
| Python libs (strategic) | manual | manual | manual | immediate |

For GitHub Actions and Docker, cool-down is enforced by Dependabot's `cooldown:` block in `.github/dependabot.yml`.

For Python libraries, the cool-down is applied **manually** via `requirements/constraints.txt`. When a new release of a strategic library (e.g. `pydantic`, `aiohttp`, `sqlalchemy`) is published, add an upper bound to `constraints.txt` (e.g. `pydantic<2.12.0`) and remove it only after the release has been validated in CI and staging. Security updates always bypass this — apply them immediately regardless of cool-down.

## References

1. [pip] manual
1. [Better Python Dependency Management with pip-tools](https://www.caktusgroup.com/blog/2018/09/18/python-dependency-management-pip-tools/) by D. Poirier
1. [Setup vs requirements] by D. Stufft
1. [Pin your packages](https://nvie.com/posts/pin-your-packages/) by V. Driessen
1. [Using pip-tools to manage my python dependencies](https://alexwlchan.net/2017/10/pip-tools/) by alexwlchan
1. [A successful pip-tools workflow for managing Python package requirements](https://jamescooke.info/a-successful-pip-tools-workflow-for-managing-python-package-requirements.html) by J. Cooke
1. [Python Application Dependency Management in 2018](https://hynek.me/articles/python-app-deps-2018/#pip-tools-everything-old-is-new-again) by Hynek Schlawack
1. [Dealing with dependency conflicts](https://pip.pypa.io/en/latest/topics/dependency-resolution/#dealing-with-dependency-conflicts) in [pip] doc

[pip-tools]:https://github.com/jazzband/pip-tools
[uv]:https://github.com/astral-sh/uv
[pip]:https://pip.pypa.io/en/stable/reference/
[pipkit-repo]:https://github.com/ITISFoundation/dockerfiles/tree/master/pip-kit
[Setup vs requirements]:https://caremad.io/posts/2013/07/setup-vs-requirement/
