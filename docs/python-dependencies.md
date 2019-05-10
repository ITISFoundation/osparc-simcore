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

!-->

## Rationale

Every python package specifies its dependencies to the installer via the ``setup.py``. Typically, dependencies to third-party libraries are listed in a text file denoted as the *requirements* file. Notice that the requirements must be in sync with the ``install_requires`` entry in the ``setup.py`` (see [Setup vs requirements]).

- All dependency specifications are under ``requirements`` folder
- There are two type of files there with extensions ``*.in`` and ``*.txt``
- All ``*.in`` files contain third-party dependencies
  - created by the developer
  - should not be very restrictive with versions. Add only contraints that must be enforced: e.g. to fix vulnerabilities, compatibility issues, etc
  - used as input to [pip-tools] which will determine the final version used
- All ``*.txt`` files are actual requirements, i.e. can be used in ``pip install -r requirements/filename.txt``. There are two types:
  1. *frozen dependencies* are automaticaly created using [pip-tools] from ``_*.in`` files. These includes a strict list of libraries with pinned versions. Every ``_*.in`` file has a ``_*.txt`` counterpart. **Notice** that these files start with ``_`` and therefore are listed at the top of the tree.
  2. installation *shortcuts* for three different *contexts*:
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

1. Needs to install [pip-tools]
   - polutes the venv
   - **SOLUTION** under devlopment: [pip-kit](https://github.com/ITISFoundation/dockerfiles/tree/master/pip-kit) is a containarized solution with multiple packages
1. Requirements from in-place packages are not accounted in services upon *pip-compilation* since they cannot be added to ``_base.txt`` or ``_test.txt`` !!!!!!
1. Adding dependencies to **in-place simcore's repo packages** is error-prone since it requires changes in multiple places, namely:
   - paths entries in ``requirements/[dev|ci|prod].txt``
   - package names+version in requirements list for ``setup.py``
1. Cannot use [pip-tools] (e.g. ``pip-sync``) with ``requirements/ci.txt`` or ``requirements/prod.txt`` because of in-place dependencies: ``pip-compile does not support URLs as packages, unless they are editable. Perhaps add -e option? (constraint was: file:///home/crespo/devp/osparc-simcore/packages/s3wrapper (from -r requirements/ci.txt (line 13)))``

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


## References

1. [pip] manual
1. [Better Python Dependency Management with pip-tools](https://www.caktusgroup.com/blog/2018/09/18/python-dependency-management-pip-tools/) by D. Poirier
1. [Setup vs requirements] by D. Stufft
1. [Pin your packages](https://nvie.com/posts/pin-your-packages/) by V. Driessen
1. [Using pip-tools to manage my python dependencies](https://alexwlchan.net/2017/10/pip-tools/) by alexwlchan
1. [A successful pip-tools workflow for managing Python package requirements](https://jamescooke.info/a-successful-pip-tools-workflow-for-managing-python-package-requirements.html) by J. Cooke


[pip-tools]:https://github.com/jazzband/pip-tools
[pip]:https://pip.pypa.io/en/stable/reference/
[pipkit-repo]:https://github.com/ITISFoundation/dockerfiles/tree/master/pip-kit
[Setup vs requirements]:https://caremad.io/posts/2013/07/setup-vs-requirement/
