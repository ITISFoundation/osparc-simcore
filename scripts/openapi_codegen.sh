#/bin/bash
#
# TODO: Uses https://github.com/OpenAPITools tools instead of swagger-codegen.
#  THIS IS THE LAST VERSION!
#    https://github.com/OpenAPITools/openapi-generator/blob/master/docs/migration-from-swagger-codegen.md
#
# https://github.com/OpenAPITools/openapi-generator/releases/tag/v3.0.0
# https://angular.schule/blog/2018-06-swagger-codegen-is-now-openapi-generator

#docker run --rm -v ${PWD}:/local openapitools/openapi-generator-cli generate \
#    -i https://raw.githubusercontent.com/openapitools/openapi-generator/master/modules/openapi-generator/src/test/resources/2_0/petstore.yaml \
#    -g html2 \
#    -o /local/out/html2

#docker run --rm -v ${PWD}:/local openapitools/openapi-generator-cli generate \
#    -i swagger.yaml
#    --generator-name html2 \
#    -o /local/out/python

usage()
{
    echo "usage: openapi_codegen [[[-i input] [-o output directory] [-g generator]] | [-h help]]"
}

##### Main

input_file= 
output_directory= 
generator= 
# process arguments
while [ "$1" != "" ]; do
    case $1 in
        -i | --input )          shift
                                input_file=$1
                                ;;
        -o | --outdir )         shift
                                output_directory=$1
                                ;;
        -g | --generator )      shift
                                generator=$1
                                ;;
        -h | --help )           usage
                                exit
                                ;;
        * )                     usage
                                exit 1
    esac
    shift
done

VERSION=$(uname -a);
MICROSOFT_STRING="Microsoft"
# SAN this is a hack so that docker works in the linux virtual environment under Windows
if echo "$VERSION" | grep -q "$MICROSOFT_STRING"; then
export DOCKER_COMPOSE=docker-compose.exe
export DOCKER=docker.exe
export COMPOSE_CONVERT_WINDOWS_PATHS=1
else
export DOCKER_COMPOSE=docker-compose
export DOCKER=docker
fi

if [ -z "$input_file" ]; then
    echo "no specification file defined..."
    usage
    exit 1
elif [ -z "$output_directory" ]; then
    echo "please define an output directory..."
    usage
    exit 1
elif [ -z "$generator" ]; then
    echo "please define a generator..."
    usage
    exit 1
fi

input_file_absolute_path="$(realpath "${input_file}")"
input_parent_dir="$(dirname "${input_file_absolute_path}")"
input_filename="$(basename "${input_file_absolute_path}")"
echo "input file parent dir is ${input_parent_dir}"
echo "input file name is ${input_filename}"

output_absolute_dir="$(realpath ${output_directory})"
echo "output directory is ${output_absolute_dir}"

if echo "$VERSION" | grep -q "$MICROSOFT_STRING"; then
# if windows WSL we need to correct the mounted path to be understandable for docker
# /mnt/k/folder/subfolder/... -> k:/folder/subfolder/...
input_parent_dir=$(echo $input_parent_dir | sed -e 's,/mnt/\(.\)/,\1:/,')
echo "windows corrected input directory is ${input_parent_dir}"
output_absolute_dir=$(echo $output_absolute_dir | sed -e 's,/mnt/\(.\)/,\1:/,')
echo "windows corrected output directory is ${output_absolute_dir}"
fi

echo "generating code..."
exec ${DOCKER} run --rm -v ${input_parent_dir}:/local -v ${output_absolute_dir}:/output openapitools/openapi-generator-cli \
    generate \
    -i /local/${input_filename} \
    -g ${generator} \
    -o /output/${generator}
echo "code generated"