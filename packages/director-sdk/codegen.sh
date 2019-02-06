#/bin/bash
docker build ../../scripts/openapi/oas_resolver -t oas_resolver
docker run -v ${PWD}/../../api/specs:/input -v ${PWD}:/output oas_resolver /input/director/v0/openapi.yaml /output/output_file.yaml

../../scripts/openapi/openapi_codegen.sh \
    -i output_file.yaml \
    -o . \
    -g python \
    -c ./codegen_config.json
