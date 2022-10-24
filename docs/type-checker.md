# Type checker


- We use [mypy] (intro in [mypy-doc])
- Single repo-wide ``mypy.ini`` configuration at the osparc base folder
- ``make mypy`` recipe is exposed at every ``packages`` or ``services`` module. It runs [mypy] on the ``src`` folder
-




[mypy-doc]:https://mypy.readthedocs.io/en/latest/
[mypy]:http://mypy-lang.org/
