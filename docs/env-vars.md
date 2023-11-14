# Environment variables management

As a developer you will need to extend the current env vars for a service.

The following rules must be followed:

1. for each service that requires it, add it to the `services/docker-compose.yml` file (such as `MY_VAR=${MY_VAR}`)
2. add a meaningful default value for development inside `.env-devel` so that developers can work, and that `osparc-simcore` is **self contained**.
  - **NOTE** if the variable has a default inside the code, put the same value here
3. inside the repo where devops keep all the secrets follow the instructions to add the new env var
