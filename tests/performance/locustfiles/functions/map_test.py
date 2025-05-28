# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "osparc>=0.8.3.post0.dev26",
#     "tenacity",
# ]
# ///


import json
import os
import time
import zipfile
from pathlib import Path

# import osparc
import osparc_client

_SCRIPT_DIR = Path(__file__).parent
_MAIN_FILE = _SCRIPT_DIR / "main.py"
assert _MAIN_FILE.is_file(), f"Main file not found: {_MAIN_FILE}"
_NERVE_MODEL_FILE = _SCRIPT_DIR / "Nerve_Model.sab"
assert _NERVE_MODEL_FILE.is_file(), f"Nerve model file not found: {_NERVE_MODEL_FILE}"
_VALUES_FILE = _SCRIPT_DIR / "values.json"
assert _VALUES_FILE.is_file(), f"Values file not found: {_VALUES_FILE}"

_SOLVER_KEY = "simcore/services/comp/s4l-python-runner"
_SOLVER_VERSION = "1.2.200"


def main():
    url = os.environ.get("OSPARC_API_URL")
    assert url
    key = os.environ.get("OSPARC_API_KEY")
    assert key
    secret = os.environ.get("OSPARC_API_SECRET")
    assert secret
    configuration = osparc_client.Configuration(host=url, username=key, password=secret)

    uploaded_files = []
    registered_functions = []

    with osparc_client.ApiClient(configuration) as api_client:
        try:
            api_instance = osparc_client.FunctionsApi(api_client)
            job_api_instance = osparc_client.FunctionJobsApi(api_client)
            job_collection_api_instance = osparc_client.FunctionJobCollectionsApi(
                api_client
            )
            file_client_instance = osparc_client.FilesApi(api_client)
            user_api_instance = osparc_client.UsersApi(api_client)

            user_api_instance.get_my_profile()

            main_file = file_client_instance.upload_file(file=f"{_MAIN_FILE.resolve()}")
            assert main_file.id
            uploaded_files.append(main_file)

            nerve_model_file = file_client_instance.upload_file(
                file=f"{_NERVE_MODEL_FILE.resolve()}"
            )
            assert nerve_model_file.id
            uploaded_files.append(nerve_model_file)

            values_file = file_client_instance.upload_file(
                file=f"{_VALUES_FILE.resolve()}"
            )
            assert values_file.id
            uploaded_files.append(values_file)

            solver_function = osparc_client.Function(
                osparc_client.SolverFunction(
                    uid=None,
                    title="SincSolver",
                    description="2D sinc using solver",
                    input_schema=osparc_client.JSONFunctionInputSchema(),
                    output_schema=osparc_client.JSONFunctionOutputSchema(),
                    solver_key=_SOLVER_KEY,
                    solver_version=_SOLVER_VERSION,
                    default_inputs={"input_1": main_file, "input_2": nerve_model_file},
                )
            )
            print(f"Built function: {solver_function.to_dict()}\n")

            registered_function = api_instance.register_function(
                solver_function.model_dump()
            )

            print(f"Registered function: {registered_function.to_dict()}\n")

            function_id = registered_function.to_dict().get("uid")
            assert function_id

            received_function = api_instance.get_function(function_id)

            function_job = api_instance.run_function(
                function_id, {"input_3": values_file}
            )

            function_job_uid = function_job.to_dict().get("uid")
            assert function_job_uid

            while (
                job_status := job_api_instance.function_job_status(
                    function_job_uid
                ).status
            ) not in ("SUCCESS", "FAILED"):
                print(f"Job status: {job_status}")
                time.sleep(5)
            print(f"Job status: {job_status}")

            job_output_dict = job_api_instance.function_job_outputs(function_job_uid)
            print(f"\nJob output: {job_output_dict}")

            downloaded_file = file_instance.download_file(
                job_output_dict["output_1"]["id"],
                destination_folder=pl.Path("./solver_files"),
            )
            print(f"Downloaded file: {downloaded_file}")
            with zipfile.ZipFile(downloaded_file, "r") as zip_file:
                job_output = json.loads(
                    zip_file.read("function_outputs.json").decode("utf-8")
                )

            print(f"Job output: {job_output}")

        finally:

            for file in uploaded_files:
                try:
                    file_client_instance.delete_file(file.id)
                    print(f"Deleted file {file.id}")
                except Exception as e:
                    print(f"Failed to delete file {file.id}: {e}")


if __name__ == "__main__":
    main()
