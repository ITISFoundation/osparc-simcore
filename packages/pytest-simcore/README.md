# pytest-simcore plugin

pytest plugin with fixtures and test helpers for osparc-simcore repo modules

## Installation

To install in a modules (e.g. web/server):

- add relative path in ``module/requirements/dev.txt`` and ``module/requirements/ci.txt`` to install for testing
- in the code, activate different fixtures by declaring the different submodules
- helper functions are imported as in a normal module


```python
from pytest_simcore.helpers.utils_assert import foo

pytest_plugins = ["pytest_simcore.environs"]


def test_something( some_pytest_simcore_fixture, ... )
    ...
```
