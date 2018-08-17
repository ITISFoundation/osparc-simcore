#/bin/sh
#
# Executes swagger-codegen-cli
#
# Source:
#    https://swagger.io/docs/open-source-tools/swagger-codegen/
#
# Image: swaggerapi/swagger-codegen-cli
#    https://github.com/swagger-api/swagger-codegen/blob/master/modules/swagger-codegen-cli/Dockerfile
#
# Usage: https://github.com/swagger-api/swagger-codegen
#
echo "The script you are running has basename `basename "$0"`, dirname `dirname "$0"`"
echo "The present working directory is `pwd`"

if [[ $# -eq 0 ]] ; then
    OPENAPI_DEFINITION="/local/`dirname "$0"`/director_api.yaml"
    #LANGUAGE=python-flask
    LANGUAGE=javascript
else
    OPENAPI_DEFINITION="/local/$1"
    LANGUAGE=$2
fi


echo "Setup -----------------------"
echo "cwd       : ${PWD} "
echo "input-spec: ${OPENAPI_DEFINITION}"
echo "language  : ${LANGUAGE}"
echo "----------------------------"

docker run --rm -v ${PWD}:/local swaggerapi/swagger-codegen-cli generate \
    --input-spec ${OPENAPI_DEFINITION} \
    --lang ${LANGUAGE} \
    --output /local/codegen-out/${LANGUAGE}
