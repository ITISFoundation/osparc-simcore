# Management of python dependencies

Since [issue 234](https://github.com/ITISFoundation/osparc-simcore/issues/234) the management of thirdparty dependencies for python packages and services is normalized.

- All dependency specifications are under ``requirements`` folder
- All ``*.in`` files are user-level specs
  - should not be very restrictive with versions. Let [pip-tools] determine the version
- Frozen list of dependency requirements are automaticaly created using [pip-tools] into ``*.txt`` files
- ``setup.py`` reads these files into the package setup
  - for libraries, i.e in [packages](../packages), reads ``base.in`` into its requirements while for [services](../services) it reads ``base.txt``.
  - Library dependencies are more flexible while in the services requirments are strict.
- ``requirements/dev.txt`` is a special shortcut for development. It installs the package in [develop (or edit)](https://pip.pypa.io/en/stable/reference/pip_install/#usage) mode as well as  other tools or packages whithin the simcore repository


## [pip-tools] workflow

![](https://github.com/jazzband/pip-tools/raw/master/img/pip-tools-overview.png)


### compling package requirements

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

### developing a package

We use directly [pip]

```console
$ cd path/to/package
$ pip install -r requirements/dev.txt
```


[pip-tools]:https://github.com/jazzband/pip-tools
[pip]:https://pip.pypa.io/en/stable/reference/
