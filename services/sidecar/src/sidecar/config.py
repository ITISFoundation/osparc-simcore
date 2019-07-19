import os

SERVICES_MAX_NANO_CPUS = os.environ.get("SERVICES_MAX_NANO_CPUS", 4)
SERVICES_MAX_MEMORY_BYTES = os.environ.get("SERVICES_MAX_MEMORY_BYTES", 2 * pow(1024, 3))
SERVICES_TIMEOUT_SECONDS = os.environ.get("SERVICES_TIMEOUT_SECONDS", 15*60)
SWARM_STACK_NAME = os.environ["SWARM_STACK_NAME"]