# Management of python dependencies

Since [issue 234](https://github.com/ITISFoundation/osparc-simcore/issues/234) the management of thirdparty dependencies for python packages and services is normalized.


- All dependency specifications are under ``requirements`` folder
- There are two type of files there with extensions ``*.in`` and ``*.txt``
- All ``*.in`` files contain third-party dependenices
  - created by the developer
  - should not be very restrictive with versions. Add only contraints that must be enforced: e.g. to fix vulnerabilities, compatibility issues, etc
  - used as input to [pip-tools] which will determine the final version used
- All ``*.txt`` files are actual requirements, i.e. can be used in ``pip install -r requirements/filename.txt``. There are two types:
  1. *frozen dependencies* are automaticaly created using [pip-tools] from ``*.in`` files. These includes a strict list of libraries with pinned versions. Every ``*.in`` file has a ``*.txt`` counterpart.
  1. installation *shortcuts* for three different *contexts*:
     1. **development**: ``pip install -r requirements/dev.txt``
        - Installs target package in [develop (or edit)](https://pip.pypa.io/en/stable/reference/pip_install/#usage) mode as well as  other tools or packages whithin the simcore repository
     2. **contiguous integration**: ``pip install -r requirements/ci.txt``
        - Installs target package, simcore-repo  and tests dependencies
     3. **production**: ``pip install -r requirements/prod.txt``
        - Installs target package  and simcore-repo dependencies
- ``setup.py`` read dependencies into the setup
  - for libraries, i.e in [packages](../packages), reads ``base.in`` into its requirements while for [services](../services) it reads ``base.txt``.
  - Library dependencies are more flexible while in the services requirements are strict.
  - Dependencies from simcore-repo's packages, installed via the shortcut requirements, are explicitly appended by hand.

## [pip-tools] workflow

1. developer **only** sets ``*.in`` files (or the shortcut files)
2. ``pip-compile`` requirements
3. ``pip install -r requirements/[dev|ci|prod].txt`` depending on your context

![](https://github.com/jazzband/pip-tools/raw/master/img/pip-tools-overview.png)


### compiling requirements

or how to convert all ``requirements/*.in`` into ``requirements/*.txt``

```console
$ cd path/to/package/requirements
$ make help
all – pip-compiles all requirements/*.in -> requirements/*.txt
check – Checks whether pip-compile is installed
clean – Cleans all requirements/*.txt (except dev.txt)
help – Display all callable targets
$ make
```

### developing context

We use directly [pip]

```console
$ cd path/to/package
$ pip install -r requirements/dev.txt
```


[pip-tools]:https://github.com/jazzband/pip-tools
[pip]:https://pip.pypa.io/en/stable/reference/
[pipkit-repo]:https://github.com/ITISFoundation/dockerfiles/tree/master/pip-kit
