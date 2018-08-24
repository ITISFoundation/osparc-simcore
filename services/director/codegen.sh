#!/bin/bash
input=./src/director/.openapi/v1/director_api.yaml
outputdir=./src/director/generated_code
absinputpath=$(realpath "${input}")
absoutputdir=$(realpath "${outputdir}")
../../scripts/openapi/openapi_python_server_codegen.sh -i ${absinputpath} -o ${absoutputdir}
find src/director/generated_code/ -type f -exec sed -i 's/openapi_server/director.generated_code/g' {} \;