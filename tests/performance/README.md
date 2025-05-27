# osparc-simcore Performance Test Suite

This directory contains performance testing tools and scripts for osparc-simcore, using [Locust](https://locust.io/) for load testing. The suite is designed for both interactive (developer) and CI (automation) usage, with robust credential/config prompts and support for result visualization in Grafana.

## Makefile Targets

All main operations are managed via the provided `Makefile`. Ensure you have a Python virtual environment activated and all dependencies installed before running the targets.

### Main Targets

- **`make test-deployment`**
  Interactively prompts for credentials and Locust configuration, then runs a Locust test. If required files are missing, you will be prompted for:
  - SC (Simcore) username and password
  - Optionally, OSPARC username and password (press Enter to skip)
  - Locust configuration (target host, users, etc.)
  - Locust file selection: a list of available `.py` files (excluding `__init__.py`) and `workflow.py` in subfolders will be shown; enter the path to the desired file.

- **`make test-deployment-with-grafana`**
  Like `test-deployment`, but also starts Grafana dashboards for monitoring. Prompts for credentials and configuration if needed.

- **`make test-deployment-ci`**
  Runs a Locust test in CI mode. Expects `.auth-credentials.env` and `.locust.conf` to already exist (no prompts). Fails if these files are missing. Use this for automation and CI pipelines.

- **`make clear-credentials`**
  Removes cached credentials (`.auth-credentials.env`).

- **`make clear-locust-config`**
  Removes Locust configuration files (`.locust.conf`).

- **`make clear`**
  Removes both credentials and Locust config files.



## Locust File Selection

When prompted to select a Locust file, the script will list all available `.py` files (excluding `__init__.py`) and any `workflow.py` in subfolders. Enter the path to the file you wish to use (e.g., `locustfiles/deployment_max_rps_single_endpoint.py`).

## Visualizing Test Results with Locust UI

When running Locust (`make test-deployment`), open the following website in your browser to visualize the performance test dashboards:

- [http://127.0.0.1:8089/](http://127.0.0.1:8089/)

## Visualizing Test Results with Grafana

When running with Grafana integration (`make test-deployment-with-grafana`), open the following website in your browser to visualize the performance test dashboards:

- [http://127.0.0.1:3000/](http://127.0.0.1:3000/)

## Example: Running in CI

To use the `test-deployment-ci` target in a CI pipeline (e.g., GitLab CI), you must first generate the required files non-interactively. For example:

```sh
# Set credentials as environment variables (in CI, use CI/CD secrets)
export SC_USER_NAME=youruser
export SC_PASSWORD=yourpass
# Optionally for osparc login
export OSPARC_USER_NAME=osparcuser
export OSPARC_PASSWORD=osparcpass

# Create the credentials file
cat <<EOF > .auth-credentials.env
SC_USER_NAME=$SC_USER_NAME
SC_PASSWORD=$SC_PASSWORD
OSPARC_USER_NAME=$OSPARC_USER_NAME
OSPARC_PASSWORD=$OSPARC_PASSWORD
EOF

# Create a Locust config file (adjust locustfile path as needed)
cat <<EOF > .locust.conf
[locust]
locustfile = ./locustfiles/deployment_max_rps_single_endpoint.py
host = http://127.0.0.1:9081
users = 10
spawn-rate = 1
run-time = 5m
processes = 4
loglevel = INFO
EOF

# Run the CI target
make test-deployment-ci
```

In a GitLab CI YAML job, you can use these steps in the `script:` section, using CI/CD variables for secrets.

---

For more details, see the Makefile and comments in this directory. If you encounter issues or need to update the workflow, please refer to the latest Makefile and scripts for guidance.
