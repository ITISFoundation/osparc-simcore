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

  # for development
  pip install -r requirements/dev.txt

  # or for production
  pip install .
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


## TODO

  - [ ] cookiecutters to assist creation of modules w/ or w/o entrypoints


[simcore]:https://github.com/pcrespov/osparc-simcore
