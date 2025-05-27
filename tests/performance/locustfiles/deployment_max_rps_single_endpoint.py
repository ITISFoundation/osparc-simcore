#
# SEE https://docs.locust.io/en/stable/quickstart.html
#
# This script allows testing the maximum RPS against a single endpoint.
# Usage:
#   locust -f deployment_max_rps_single_endpoint.py --endpoint /v0/health
#
# If no endpoint is specified, the root endpoint ("/") will be used by default.
#


from common.base_user import OsparcWebUserBase
from locust import events, task
from locust.argument_parser import LocustArgumentParser


# Register the custom argument with Locust's parser
@events.init_command_line_parser.add_listener
def _(parser: LocustArgumentParser) -> None:
    parser.add_argument(
        "--endpoint",
        type=str,
        default="/",
        help="The endpoint to test (e.g., /v0/health)",
    )


class WebApiUser(OsparcWebUserBase):
    @task
    def get_endpoint(self) -> None:
        self.authenticated_get(self.environment.parsed_options.endpoint)
