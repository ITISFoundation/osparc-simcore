# Management of python dependencies

Since [issue 234](https://github.com/ITISFoundation/osparc-simcore/issues/234) the management of thirdparty dependencies for python packages and services is normalized.


- All dependency specifications are under ``requirements`` folder
- There are two type of files there with extensions ``*.in`` and ``*.txt``
- All ``*.in`` files contain third-party dependencies
  - created by the developer
  - should not be very restrictive with versions. Add only contraints that must be enforced: e.g. to fix vulnerabilities, compatibility issues, etc
  - used as input to [pip-tools] which will determine the final version used
- All ``*.txt`` files are actual requirements, i.e. can be used in ``pip install -r requirements/filename.txt``. There are two types:
  1. *frozen dependencies* are automaticaly created using [pip-tools] from ``_*.in`` files. These includes a strict list of libraries with pinned versions. Every ``_*.in`` file has a ``_*.txt`` counterpart. **Notice** that these files start with ``_`` and therefore are listed at the top of the tree.
  1. installation *shortcuts* for three different *contexts*:
     1. **development**: ``pip install -r requirements/dev.txt``
        - Installs target package in [develop (or edit)](https://pip.pypa.io/en/stable/reference/pip_install/#usage) mode as well as  other tools or packages whithin the simcore repository
     2. **contiguous integration**: ``pip install -r requirements/ci.txt``
        - Installs target package, simcore-repo  and tests dependencies
     3. **production**: ``pip install -r requirements/prod.txt``
        - Installs target package  and simcore-repo dependencies
- ``setup.py`` read dependencies into the setup
  - **libraries** (e.g. in [packages/service-lib](../packages/service-library/setup.py)) have *flexible dependencies*, i.e. requirements read from  ``requirements/_base.in``
  - **services** (e.g. in [services/web/server](../services/web/server/setup.py) ) have *strict dependencies* and therefore it reads from ``requirements/_base.txt`` where all versions are pinned.

### Limitations [May 6, 2019]
  - Adding dependencies to **in-place simcore's repo packages** is error-prone since it requires changes in multiple places, namely:
    - paths entries in ``requirements/[dev|ci|prod].txt``
    - package names+version in requirements list for ``setup.py``
  - Cannot use [pip-tools] (e.g. ``pip-sync``) with ``requirements/ci.txt`` or ``requirements/prod.txt`` because of in-place dependencies: ``pip-compile does not support URLs as packages, unless they are editable. Perhaps add -e option? (constraint was: file:///home/crespo/devp/osparc-simcore/packages/s3wrapper (from -r requirements/ci.txt (line 13)))``

## Workflows

To install a given workflow we use directly [pip]. Assume we are in the package folder

```console
$ cd path/to/package
```
then to **develop** your library/service type
```console
$ pip install -r requirements/dev.txt
```
for **CI** of your your library/service (normally used in ops/travis/...) type
```console
$ pip install -r requirements/ci.txt
```
to **deploy** your service
```console
$ pip install -r requirements/prod.txt
```
or if it is a library, then ``pip install .`` is prefered.


### Updating dependencies

This is the typical [pip-tools] workflow

1. developer **only** sets ``*.in`` files (or the shortcut files)
2. ``pip-compile`` requirements
3. ``pip install -r requirements/[dev|ci|prod].txt`` depending on your context

![](https://github.com/jazzband/pip-tools/raw/master/img/pip-tools-overview.png)


### auto-compile requirements

or how to convert all ``requirements/*.in`` into ``requirements/*.txt`` using ``requirements/Makefile``:

```console
$ cd path/to/package/requirements
$ make help
all – pip-compiles all requirements/*.in -> requirements/*.txt
check – Checks whether pip-compile is installed
clean – Cleans all requirements/*.txt (except dev.txt)
help – Display all callable targets
$ make
```



[pip-tools]:https://github.com/jazzband/pip-tools
[pip]:https://pip.pypa.io/en/stable/reference/
[pipkit-repo]:https://github.com/ITISFoundation/dockerfiles/tree/master/pip-kit
