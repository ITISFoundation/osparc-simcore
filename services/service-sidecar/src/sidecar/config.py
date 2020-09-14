import uuid

from environs import Env

env = Env()
env.read_env()  # read .env file, if it exists

# The project name for docker-compose must be unique in the entire cluster
# to avoid collisions when scheduling ont the same node.
# While it is unlikely to obtain a uuid, to avoid future problems
# The combined final name is limited to 255 characters by default,
# this is checked before creating the containers
compose_namespace = env("COMPOSE_NAMESPACE", str(uuid.uuid4()))
max_combined_container_name_length = env.int("MAX_CONTAINER_NAME_LENGTH", 255)

# When receiving SIGTERM the process has 10 seconds to cleanup its children
# forcing our children to stop in 5 seconds in all cases
stop_and_remove_timeout = env.int("STOP_AND_REMOVE_TIMEOUT", 5)
