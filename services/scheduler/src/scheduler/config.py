from environs import Env

env = Env()
env.read_env()  # read .env file, if it exists

# OSPARC
# used to distinguish between multiple deployments
swarm_stack_name = env("SWARM_STACK_NAME", "")

# Redis endpoint configuration
redis_host = env("REDIS_HOST", "redis")
redis_port = env.int("REDIS_PORT", 6379)

# MongoDB endpoint URI
mongo_uri = env("MONGO_DB_URI", "mongodb://localhost:27017")
mongo_db_name = env("MONGO_DB_NAME", "scheduler")

# OpenTracing backend Jager in this case
# Only the hostname is required the port is default to
jaeger_host = env("JAEGER_HOST", "220cf02b2dd0")
open_tracing_logging = env.bool("OPEN_TRACING_LOGGING", False)
