#/bin/bash
# FIXME: unify scripts #281
OAS=/home/guidon/devel/src/osparc-simcore/services/storage/src/simcore_service_storage/oas3/v0/openapi.yaml
source /home/guidon/devel/src/osparc-simcore/.venv/bin/activate
pip install prance
pip install openapi_spec_validator
prance compile --backend=openapi-spec-validator $OAS output.yaml

exec /home/guidon/devel/src/osparc-simcore/scripts/openapi/openapi_codegen.sh \
    -i output.yaml \
    -o . \
    -g python \
    -c ./codegen_config.json
