import re
from typing import Final

import parse
from pydantic import ByteSize

DEFAULT_COMPUTATIONAL_EC2_FORMAT: Final[
    str
] = r"osparc-computational-cluster-{role}-{swarm_stack_name}-user_id:{user_id:d}-wallet_id:{wallet_id:d}"
DEFAULT_DYNAMIC_EC2_FORMAT: Final[str] = r"osparc-dynamic-autoscaled-worker-{key_name}"
DEPLOY_SSH_KEY_PARSER: Final[parse.Parser] = parse.compile(
    r"{base_name}-{random_name}.pem"
)

MINUTE: Final[int] = 60
HOUR: Final[int] = 60 * MINUTE


SSH_USER_NAME: Final[str] = "ubuntu"
UNDEFINED_BYTESIZE: Final[ByteSize] = ByteSize(-1)
TASK_CANCEL_EVENT_NAME_TEMPLATE: Final[str] = "cancel_event_{}"

# NOTE: service_name and service_version are not available on dynamic-sidecar/dynamic-proxies!
DYN_SERVICES_NAMING_CONVENTION: Final[re.Pattern] = re.compile(
    r"^dy-(proxy|sidecar)(-|_)(?P<node_id>.{8}-.{4}-.{4}-.{4}-.{12}).*\t(?P<created_at>[^\t]+)\t(?P<user_id>\d+)\t(?P<project_id>.{8}-.{4}-.{4}-.{4}-.{12})\t(?P<service_name>[^\t]*)\t(?P<service_version>.*)$"
)

DANGER = "[red]{}[/red]"
