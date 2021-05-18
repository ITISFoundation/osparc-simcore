# performance testing using [locust.io](https://docs.locust.io/en/stable/index.html)

Locust allows simple testing of endpoints, and checks for response time, response type. It also allows to create useful reports.

## configuration

In the [locust_files] folder are located the test files.

## Usage

```console
# builds the distributed locust worker/master image
make build
# runs the test defined by locust_files/platform_ping_test.py going to http://127.0.0.1:8089 allows to see the UI
make up target=platform_ping_test.py
# removes the containers
make down
```

## Usage in CI (headless mode)

```console
# builds the distributed locust worker/master image
make build
# runs the test defined by locust_files/platform_ping_test.py in headless mode
make test target=platform_ping_test.py
# removes the containers
make down
```
