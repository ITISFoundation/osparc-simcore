# osparc-simcore CodSpeed benchmarks

Micro-benchmarks of the CPU-bound building blocks shared by all osparc services.
They are measured continuously in CI with [CodSpeed](https://codspeed.io) using
`pytest-codspeed`, so that performance regressions are caught in the pull request
that introduces them.

Reports are published at
[app.codspeed.io/ITISFoundation/osparc-simcore](https://app.codspeed.io/ITISFoundation/osparc-simcore).

## What is measured

| File                                | Covers                                                                              |
| ----------------------------------- | ----------------------------------------------------------------------------------- |
| `test_json_serialization.py`        | `common_library.json_serialization` (orjson-based `json_dumps`/`json_loads`)         |
| `test_error_codes.py`               | `common_library.error_codes` (OEC creation/parsing on error paths)                   |
| `test_projects_models.py`           | `models_library.projects` validation and serialization of a study                    |
| `test_services_models.py`           | service metadata models and json-schema validation of service ports                  |
| `test_rest_pagination.py`           | `models_library.rest_pagination` envelopes and `common_library` dict/sequence tools  |
| `test_settings.py`                  | `settings_library` settings built from environment variables                         |
| `test_substitutions_and_case.py`    | `models_library.utils` spec substitutions and case conversions                       |

## Writing a benchmark

Benchmarks are plain `pytest` tests that use the `benchmark` fixture provided by
`pytest-codspeed`:

```python
def test_something(benchmark):
    result = benchmark(my_function, arg)
    assert result  # assertions are still welcome
```

Guidelines:

- **No I/O**: no network, no database, no docker, no filesystem. These benchmarks
  run under CPU simulation (`valgrind`), which only measures CPU work, and any
  I/O would make the measurement unstable.
- **Keep the setup out of the measured callable**: build the payloads in fixtures
  (preferably module/session scoped) and only measure the call of interest.
- **Use realistic payloads**: sizes and shapes close to what the platform handles
  in production (e.g. a study with ~50 nodes).
- **Keep it deterministic**: no randomness, no `datetime.now()`-dependent branching,
  no reliance on external state.

## Running locally

```bash
# from the repository root
make devenv
source .venv/bin/activate
pushd tests/benchmarks
make install-dev

# quick check (walltime, no instrumentation)
make benchmarks

# same measurement as CI (CPU simulation, requires the codspeed CLI)
codspeed run --mode simulation -- pytest --codspeed .
popd
```

SEE the [CodSpeed python documentation](https://codspeed.io/docs/benchmarks/python)
for more details.
