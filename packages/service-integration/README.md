# simcore service integration library


### installation


```cmd
pip install git+https://github.com/pcrespov/osparc-simcore.git@is1884/integration-library#egg=simcore-service-integration&subdirectory=packages/service-integration
```

### tooling

Subcommands of ``simcore-service-integrator`` CLI:
```cmd
$ simcore-service-integrator --help
Usage: simcore-service-integrator [OPTIONS] COMMAND [ARGS]...

Options:
  --version  Show the version and exit.
  --help     Show this message and exit.

Commands:
  run-creator            Creates a sh script that uses jq tool to retrieve...
  update-compose-labels  Update a docker-compose file with json files in a...

```

Makefile sample:

```Makefile
service.cli/run: $(metatada)
	# Updates adapter script from metadata in $<
	simcore-service-integrator run-creator --metadata $< --runscript $@

docker-compose-meta.yml: $(metatada)
	# Injects metadata from $< as labels
	simcore-service-integrator update-compose-labels --compose $@ --metadata $<

```


### testing

Created a pytest-plugin from submodule ``service_integration.pytest_plugin`` with fixtures and helper assert function.

A sample of ``conftest.py`` in target repo

```python
import pytest

pytest_plugins = [
    "service_integration.pytest_plugin.folder_structure",
    "service_integration.pytest_plugin.validation_data",
]

current_dir = Path(sys.argv[0] if __name__ ==
                   "__main__" else __file__).resolve().parent


@pytest.fixture(scope='session')
def project_slug_dir() -> Path:
    project_slug_dir = current_dir.parent
    assert project_slug_dir.exists()
    return project_slug_dir

```

----

 Implementing https://github.com/ITISFoundation/osparc-simcore/issues/1884
