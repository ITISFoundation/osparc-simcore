#!/bin/bash

# SAN this allows to know whether we are running in the Windows linux environment or under linux/mac
VERSION=$(uname -a);
MICROSOFT_STRING="Microsoft"

if echo "$VERSION" | grep -q "$MICROSOFT_STRING"; then
  DOCKER=docker
  export COMPOSE_CONVERT_WINDOWS_PATHS=1
  export IS_WINDOWS=1
else
  DOCKER=docker
  export IS_WINDOWS=0
fi


#
# TODO: Uses https://github.com/OpenAPITools tools instead of swagger-codegen.
#  THIS IS THE LAST VERSION!
#    https://github.com/OpenAPITools/openapi-generator/blob/master/docs/migration-from-swagger-codegen.md
#
# https://github.com/OpenAPITools/openapi-generator/releases/tag/v3.0.0
# https://angular.schule/blog/2018-06-swagger-codegen-is-now-openapi-generator

usage()
{
    echo "usage: openapi_codegen [[[-i input] [-o output directory] [-g generator] [-c configuration file]] | [-h help] | [-languages] [-config-help language]]"
}

openapi_generator=openapitools/openapi-generator-cli:v4.2.1

list_languages()
{
    exec ${DOCKER} run --rm ${openapi_generator} list
}

print_languages_config_options()
{
    exec ${DOCKER} run --rm ${openapi_generator} config-help -g $1
}

##### Main

input_file=
output_directory=
generator=
configuration=
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
        -c | --config_file )    shift
                                configuration=$1
                                ;;
        -h | --help )           usage
                                exit
                                ;;
        -languages )            list_languages
                                exit
                                ;;
        -config-help )          shift
                                print_languages_config_options $1
                                exit
                                ;;
        * )                     usage
                                exit 1
    esac
    shift
done


# check arguments
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
elif [ -z "$configuration" ]; then
    echo "using default configuration..."
fi

input_file_absolute_path="$(realpath "${input_file}")"
input_parent_dir="$(dirname "${input_file_absolute_path}")"
input_filename="$(basename "${input_file_absolute_path}")"
echo "input file parent dir is ${input_parent_dir}"
echo "input file name is ${input_filename}"

output_absolute_dir="$(realpath ${output_directory})"
echo "output directory is ${output_absolute_dir}"
if [ ! -z "$configuration" ]; then
    configuration_absolute_file_path="$(realpath ${configuration})"
    configuration_parent_dir="$(dirname "${configuration_absolute_file_path}")"
    configuration_filename="$(basename "${configuration_absolute_file_path}")"
fi

if echo "$VERSION" | grep -q "$MICROSOFT_STRING"; then
    # if windows WSL we need to correct the mounted path to be understandable for docker
    # /mnt/k/folder/subfolder/... -> k:/folder/subfolder/...
    input_parent_dir=$(echo $input_parent_dir | sed -e 's,/mnt/\(.\)/,\1:/,')
    echo "windows corrected input directory is ${input_parent_dir}"
    output_absolute_dir=$(echo $output_absolute_dir | sed -e 's,/mnt/\(.\)/,\1:/,')
    echo "windows corrected output directory is ${output_absolute_dir}"
    if [ ! -z "$configuration" ]; then
        configuration_parent_dir=$(echo $configuration_parent_dir | sed -e 's,/mnt/\(.\)/,\1:/,')
        echo "windows corrected configuration directory is ${configuration_parent_dir}"
    fi
fi


echo "generating code..."
if [ ! -z "$configuration" ]; then
  ${DOCKER} run --rm -v ${input_parent_dir}:/local -v ${output_absolute_dir}:/output -v ${configuration_parent_dir}:/config ${openapi_generator} \
    generate \
    -i /local/${input_filename} \
    -g ${generator} \
    -o /output/${generator} \
    -c /config/${configuration_filename}
else
  ${DOCKER} run --rm -v ${input_parent_dir}:/local -v ${output_absolute_dir}:/output ${openapi_generator} \
    generate \
    -i /local/${input_filename} \
    -g ${generator} \
    -o /output/${generator}
fi


sudo chown -R $USER:$USER ${output_absolute_dir}/${generator}
