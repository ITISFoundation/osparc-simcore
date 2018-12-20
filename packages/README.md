# packages

Folder for [simcore] python packages (libraries, client-sdks, programs, ... )

## Rationale

Every folder contains a python package with the following properties:

- it is *[pip]-installable* python packages

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


## Package Managemenent

 - We use [pip] as main package manager for python
 - [pipreqs] -
 - [hashin] - Helps you write your requirements.txt with hashes so you can install with ``pip install --require-hashes -r`` ...
  ```cmd
  cat requirements/base.txt | xargs hashin -r requirements/base.txt --dry-run
  cat requirements/base.txt | xargs hashin -r requirements/base.txt --verbose
  ```
 - ``requirements`` folder
   - production packages pins version and [hash](https://pip.pypa.io/en/stable/reference/pip_install/#hash-checking-mode): ``pip install --require-hashes -r requirements.txt``
   -



## TODO

  - [ ] cookiecutters to assist creation of modules w/ or w/o entrypoints



<!--
Doc reference links below
-->
[simcore]:https://github.com/itisfoundation/osparc-simcore
[pip]: https://pip.pypa.io/en/stable/reference/
[pipreqs]:https://github.com/bndr/pipreqs
[piptools]:https://github.com/jazzband/pip-tools
[pipdeptree]:https://github.com/naiquevin/pipdeptree
[hashin]:https://github.com/peterbe/hashin
[pyup]:https://pyup.io
