#!/bin/bash
# http://redsymbol.net/articles/unofficial-bash-strict-mode/
set -o errexit
set -o nounset
set -o pipefail
IFS=$'\n\t'

# points to root soruce directory of this project, usually ../../
ROOT_PROJECT_DIR=$1
# name of the job, usually defined in the .github/workflows/ci-testing-deploy.yaml
JOB_TO_RUN=$2

DOCKER_IMAGE_NAME=dind-act-runner
ACT_RUNNER=ubuntu-20.04=catthehacker/ubuntu:act-20.04
ACT_VERSION_TAG=v0.2.20 # from https://github.com/nektos/act/releases

docker buildx build --load -t $DOCKER_IMAGE_NAME - <<EOF
FROM docker:dind

RUN apk add curl bash
RUN curl -fsSL  https://raw.githubusercontent.com/nektos/act/master/install.sh | bash /dev/stdin -d $ACT_VERSION_TAG

WORKDIR /project

CMD /bin/sh -c "act -v -P $ACT_RUNNER -j $JOB_TO_RUN"
EOF

echo "$(pwd)/${ROOT_PROJECT_DIR}"
docker run --rm -it \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$(pwd)"/"${ROOT_PROJECT_DIR}":/project \
  -v "$(pwd)"/ci-logs:/logs \
  $DOCKER_IMAGE_NAME
