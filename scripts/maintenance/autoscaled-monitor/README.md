# autoscaled-monitor

CLI tool for monitoring autoscaled dynamic and computational instances on oSPARC deployments.

## Installation

```bash
cd scripts/maintenance/autoscaled-monitor
uv sync
```

## Usage

```bash
autoscaled-monitor --deploy-config PATH/TO/DEPLOYMENT summary
```

### Commands

#### `summary` — compact overview of all instances

Shows dynamic instances with their services and computational clusters with task-level details.

```bash
# Full summary
autoscaled-monitor --deploy-config PATH/TO/DEPLOYMENT summary

# Filter by user
autoscaled-monitor --deploy-config PATH/TO/DEPLOYMENT summary --user-id 123

# Filter by wallet
autoscaled-monitor --deploy-config PATH/TO/DEPLOYMENT summary --user-id 123 --wallet-id 456

# JSON output
autoscaled-monitor --deploy-config PATH/TO/DEPLOYMENT summary --as-json

# Write to file
autoscaled-monitor --deploy-config PATH/TO/DEPLOYMENT summary --output report.txt
```

#### `dynamic summary` — verbose dynamic instances view

```bash
autoscaled-monitor --deploy-config PATH/TO/DEPLOYMENT dynamic summary
autoscaled-monitor --deploy-config PATH/TO/DEPLOYMENT dynamic summary --user-id 123
```

#### `dynamic terminate` — terminate dynamic instances

```bash
autoscaled-monitor --deploy-config PATH/TO/DEPLOYMENT dynamic terminate
```

#### `computational summary` — verbose computational clusters view

```bash
autoscaled-monitor --deploy-config PATH/TO/DEPLOYMENT computational summary
autoscaled-monitor --deploy-config PATH/TO/DEPLOYMENT computational summary --user-id 123 --wallet-id 456
```

#### `computational cancel-jobs` — cancel running computational jobs

```bash
autoscaled-monitor --deploy-config PATH/TO/DEPLOYMENT computational cancel-jobs
```

#### `computational terminate` — terminate computational instances

```bash
autoscaled-monitor --deploy-config PATH/TO/DEPLOYMENT computational terminate
```

#### `db check` — test database connectivity

```bash
autoscaled-monitor --deploy-config PATH/TO/DEPLOYMENT db check
```

## Options

| Option | Description |
|--------|-------------|
| `--deploy-config PATH` | **(required)** Path to the deployment configuration directory (must contain `repo.config`, `ansible/inventory.ini`, and an SSH key `.pem` file) |

### Command-specific options

| Option | Available on | Description |
|--------|-------------|-------------|
| `--user-id INT` | `summary`, `dynamic summary`, `computational summary` | Filter by user ID |
| `--wallet-id INT` | `summary`, `computational summary` | Filter by wallet ID |
| `--as-json` | `summary`, `dynamic summary`, `computational summary` | Output as JSON |
| `--output PATH` | `summary`, `dynamic summary`, `computational summary` | Write output to file |
