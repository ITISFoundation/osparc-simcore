#
# SEE https://docs.locust.io/en/stable/quickstart.html
#
# This script allows testing running a function via the map endpoint
#


import json
from datetime import timedelta

import jsf
from common.base_user import OsparcWebUserBase
from locust import events, task
from locust.argument_parser import LocustArgumentParser
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_delay,
    wait_exponential,
)


# Register the custom argument with Locust's parser
@events.init_command_line_parser.add_listener
def _(parser: LocustArgumentParser) -> None:
    parser.add_argument(
        "--function_uid",
        type=str,
        required=True,
        help="The function UUID to test",
    )
    parser.add_argument(
        "--function-input-json-schema",
        type=str,
        required=True,
        help="JSON schema for the function job inputs",
    )
    parser.add_argument(
        "--max-poll-time-seconds",
        type=int,
        default=60,
        help="Maximum time to wait for the function job to complete",
    )


class WebApiUser(OsparcWebUserBase):
    @task
    def run_function(self) -> None:

        function_uid = self.environment.parsed_options.function_uid
        job_input_schema = json.loads(self.environment.parsed_options.body_json_schema)
        max_poll_time = timedelta(
            seconds=self.environment.parsed_options.max_poll_time_seconds
        )

        # run function
        job_input_faker = jsf.JSF(job_input_schema)
        response = self.authenticated_post(
            url=f"/v0/functions/{function_uid}:run",
            json=job_input_faker.generate(),
            headers={
                "x-simcore-parent-project-uuid": "null",
                "x-simcore-parent-node-id": "null",
            },
        )
        response.raise_for_status()
        job_uid = response.json().get("uid")

        # wait for the job to complete
        for attempt in Retrying(
            stop=stop_after_delay(max_delay=max_poll_time),
            wait=wait_exponential(multiplier=1, min=1, max=10),
            reraise=True,
            retry=retry_if_exception_type(ValueError),
        ):
            with attempt:
                job_status_response = self.authenticated_get(
                    f"/v0/function_jobs/{job_uid}/status"
                )
                job_status_response.raise_for_status()
                status = job_status_response.json().get("status")
                if status != "SUCCESS":
                    raise ValueError(
                        f"Function job ({job_uid=}) for function ({function_uid=}) returned {status=}"
                    )
