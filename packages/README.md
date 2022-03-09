# packages

Folder for [simcore] python packages (libraries, client-sdks, programs, ... )

## Rationale

Every folder contains a python package with the following properties:

- it is *pip-installable* python packages

```cmd
  # creates and activates venv
  make .venv
  source .venv/bin/activate
  cd packages/my-package
```
then for development
```cmd
  pip install -r requirements/dev.txt
  pytest tests
```
or simply (does a bit more than above)
```
make install-dev
make tests
```



- it can be a package with or without with *entrypoints*.
  - a **library** has no entrypoints
    - a collection of functions/classes organized in namespaces
    - importable: ``import mylib``
  - An entrypoint allows using the package as a stand-alone program in the shell
  ```cmd
    python -m my-distribution-name --help

    # or
    my-distribution-name --help

    # or as a lib
    >> import mylib
  ```
