#!/bin/sh
set -o errexit
set -o nounset

IFS=$(printf '\n\t')

GREEN='\033[0;32m'
NC='\033[0m' # No Color

# Function to print an INFO message in green
print_info() {
  echo "${GREEN}INFO [$(basename "$0")]:${NC}$1"
}

print_error() {
  echo "ERROR: [$(basename "$0")] $1"
}

# BOOTING application ---------------------------------------------
print_info "Booting in ${SC_BOOT_MODE} mode ..."
print_info "  User    :$(id "$(whoami)")"
print_info "  Workdir :$(pwd)"
print_info "  env     :$(env)"

if [ "${SC_BUILD_TARGET}" = "development" ]; then
  print_info "Environment :"
  printenv | sed 's/=/: /' | sed 's/^/    /' | sort
  print_info "Python :"
  python --version | sed 's/^/    /'
  command -v python | sed 's/^/    /'
  cd services/dask-sidecar
  uv pip --quiet sync --link-mode=copy requirements/dev.txt
  cd -
  print_info "PIP :"
  uv pip list
fi

if [ "${SC_BOOT_MODE}" = "debug" ]; then
  # NOTE: production does NOT pre-installs debugpy
  if command -v uv >/dev/null 2>&1; then
    uv pip install --link-mode=copy debugpy
  else
    pip install debugpy
  fi
fi

# RUNNING application ----------------------------------------
#
# - If DASK_START_AS_SCHEDULER is set, then it boots as scheduler otherwise as worker
#

mkdir --parents /home/scu/.config/dask
cat >/home/scu/.config/dask/distributed.yaml <<EOF
logging:
  distributed: ${LOG_LEVEL:-warning}
  distributed.scheduler: ${LOG_LEVEL:-warning}
EOF

# Define the base configuration for distributed
# the worker-saturation defines how the scheduler loads
# the workers, see https://github.com/dask/distributed/blob/91350ab15c79de973597e319bd36cc8d56e9f999/distributed/scheduler.py
cat >/home/scu/.config/dask/distributed.yaml <<EOF
distributed:
  scheduler:
    worker-saturation: ${DASK_WORKER_SATURATION:-inf}
EOF

# Check if DASK_TLS_CA_FILE is present and add the necessary configs
if [ -n "${DASK_TLS_CA_FILE:-}" ]; then
  print_info "TLS authentication enabled"
  cat >>/home/scu/.config/dask/distributed.yaml <<EOF
  comm:
    default-scheme: tls
    require-encryption: true
    tls:
      ca-file: ${DASK_TLS_CA_FILE}
      scheduler:
        key: ${DASK_TLS_KEY}
        cert: ${DASK_TLS_CERT}
      worker:
        key: ${DASK_TLS_KEY}
        cert: ${DASK_TLS_CERT}
      client:
        key: ${DASK_TLS_KEY}
        cert: ${DASK_TLS_CERT}
EOF
fi

#
# MEMRAY profiling (opt-in, development image only, see
# services/README.md#memory-profiling-with-memray)
#
# - DASK_SIDECAR_MEMRAY_ENABLED=true wraps 'dask scheduler'/'dask worker' with memray
# - dask forks worker processes and memray cannot combine live tracking with
#   --follow-fork, therefore 'file' (the default here) writes one capture per process
#   to DASK_SIDECAR_MEMRAY_OUTPUT_DIR. 'live' only tracks the main process.
#
is_true() {
  case "$(printf '%s' "${1:-False}" | tr '[:upper:]' '[:lower:]')" in
    true | 1) return 0 ;;
    *) return 1 ;;
  esac
}

MEMRAY_ON=False
if is_true "${DASK_SIDECAR_MEMRAY_ENABLED:-False}"; then
  if ! command -v memray >/dev/null 2>&1; then
    print_error "DASK_SIDECAR_MEMRAY_ENABLED is set but memray is not installed" \
      "(only available in the development image, see requirements/_tools.in)"
    exit 1
  fi
  MEMRAY_ON=True
fi
MEMRAY_MODE=${DASK_SIDECAR_MEMRAY_MODE:-file}
MEMRAY_PORT=${DASK_SIDECAR_MEMRAY_PORT:-10262}
MEMRAY_OUTPUT_DIR=${DASK_SIDECAR_MEMRAY_OUTPUT_DIR:-/tmp/memray}

if [ ${DASK_START_AS_SCHEDULER+x} ]; then
  scheduler_version=$(dask scheduler --version)
  print_info "Starting as dask scheduler:${scheduler_version}..."
  if [ "${SC_BOOT_MODE}" = "debug" ]; then
    exec watchmedo auto-restart \
      --recursive \
      --pattern="*.py;*/src/*" \
      --ignore-patterns="*test*;pytest_simcore/*;setup.py;*ignore*" \
      --ignore-directories -- \
      dask scheduler \
      --preload simcore_service_dask_sidecar.scheduler
  elif [ "${MEMRAY_ON}" = "True" ]; then
    # memray options MUST precede '-m dask', otherwise they are passed to dask
    set -- run
    if is_true "${DASK_SIDECAR_MEMRAY_NATIVE:-True}"; then
      set -- "$@" --native
    fi
    if [ "${MEMRAY_MODE}" = "live" ]; then
      print_info "memray live tracking: run 'memray live ${MEMRAY_PORT}' (e.g. via docker exec) ..."
      set -- "$@" --live-remote --live-port "${MEMRAY_PORT}"
    else
      mkdir -p "${MEMRAY_OUTPUT_DIR}"
      MEMRAY_OUTPUT="${MEMRAY_OUTPUT_DIR}/dask-sidecar.$(date +%Y%m%dT%H%M%SZ).${$}.bin"
      print_info "memray writing capture to ${MEMRAY_OUTPUT} ..."
      set -- "$@" --force --follow-fork --output "${MEMRAY_OUTPUT}"
    fi
    exec memray "$@" -m dask scheduler \
      --preload simcore_service_dask_sidecar.scheduler
  else
    exec dask scheduler \
      --preload simcore_service_dask_sidecar.scheduler

  fi

else
  DASK_WORKER_VERSION=$(dask worker --version)
  DASK_SCHEDULER_URL=${DASK_SCHEDULER_URL:="tls://${DASK_SCHEDULER_HOST}:8786"}

  #
  # DASK RESOURCES DEFINITION
  #
  # Following resources are defined on a dask-sidecar for computational tasks:
  # CPU: number of CPUs available (= num of processing units - DASK_SIDECAR_NUM_NON_USABLE_CPUS)
  # GPU: number GPUs available (= num of GPUs if a nvidia-smi can be run inside a docker container)
  # RAM: amount of RAM available (= CPU/nproc * total virtual memory given by python psutil - DASK_SIDECAR_NON_USABLE_RAM)
  # VRAM: amount of VRAM available (in bytes)
  # DASK_SIDECAR_CUSTOM_RESOURCES: any amount of anything (in name=NUMBER,name2=NUMBER2,..., see https://distributed.dask.org/en/stable/resources.html#worker-resources)

  # CPUs
  num_cpus=$(($(nproc) - ${DASK_SIDECAR_NUM_NON_USABLE_CPUS:-2}))
  if [ "$num_cpus" -le 0 ]; then
    # ensure the minimal amount of cpus is 1 in case the system is a dual-core or less (CI case for instance)
    num_cpus=1
  fi

  # GPUs
  num_gpus=$(python -c "from simcore_service_dask_sidecar.utils.gpus import num_available_gpus; print(num_available_gpus());")

  # RAM (is computed similarly as the default dask-sidecar computation)
  _value=$(python -c "import psutil; print(int(psutil.virtual_memory().total * $num_cpus/$(nproc)))")
  ram=$((_value - ${DASK_SIDECAR_NON_USABLE_RAM:-0}))

  # overall resources available on the dask-sidecar (CPUs and RAM are always available)
  resources="CPU=$num_cpus,RAM=$ram"

  # add the GPUs if there are any
  if [ "$num_gpus" -gt 0 ]; then
    total_vram=$(python -c "from simcore_service_dask_sidecar.utils.gpus import video_memory; print(video_memory());")
    resources="$resources,GPU=$num_gpus,VRAM=$total_vram"
  fi

  # check whether we might have an EC2 instance and retrieve its type
  get_ec2_instance_type() {
    # https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/instancedata-data-retrieval.html
    print_info "Finding out if we are running on an EC2 instance"

    # fetch headers only
    if http_response=$(curl --max-time 5 --silent --head http://169.254.169.254/latest/meta-data/instance-type 2>/dev/null); then
      # Extract the HTTP status code (e.g., 200, 404)
      http_status_code=$(echo "$http_response" | awk '/^HTTP/ {print $2}')

      if [ "$http_status_code" = "200" ]; then
        # Instance type is available
        ec2_instance_type=$(curl --max-time 5 --silent http://169.254.169.254/latest/meta-data/instance-type)
        print_info "Running on an EC2 instance of type: $ec2_instance_type"
        resources="$resources,EC2-INSTANCE-TYPE:$ec2_instance_type=1"
      else
        print_info "Not running on an EC2 instance. HTTP Status Code: $http_status_code"
      fi
    else
      print_info "Failed to fetch instance type. Not running on an EC2 instance."
    fi
  }
  get_ec2_instance_type

  #
  # DASK RESOURCES DEFINITION --------------------------------- END
  #
  DASK_NPROCS=${DASK_NPROCS:="1"}
  DASK_NTHREADS=${DASK_NTHREADS:="$num_cpus"}
  DASK_MEMORY_LIMIT=${DASK_MEMORY_LIMIT:="$ram"}
  DASK_WORKER_NAME=${DASK_WORKER_NAME:="dask-sidecar_$(hostname)_$(date +'%Y-%m-%d_%T')_$$"}
  # If DASK_NTHREADS_MULTIPLIER is defined, multiply DASK_NTHREADS (round to nearest int, min 1)
  if [ -n "${DASK_NTHREADS_MULTIPLIER:-}" ]; then
    # check DASK_NTHREADS_MULTIPLIER is a number
    if awk -v m="$DASK_NTHREADS_MULTIPLIER" 'BEGIN{ if (m+0==m) exit 0; else exit 1 }'; then
      # multiply and round to nearest int, min 1
      new_nthreads=$(awk -v n="$DASK_NTHREADS" -v m="$DASK_NTHREADS_MULTIPLIER" 'BEGIN{ r=n*m; if(r<1) r=1; printf("%d", (r==int(r)?int(r):int(r+0.5))) }')
      DASK_NTHREADS="$new_nthreads"
      print_info "DASK_NTHREADS multiplied by ${DASK_NTHREADS_MULTIPLIER} -> ${DASK_NTHREADS}"
    else
      print_info "DASK_NTHREADS_MULTIPLIER is not numeric: ${DASK_NTHREADS_MULTIPLIER}"
    fi
  fi

  #
  # 'daemonic processes are not allowed to have children' arises when running the sidecar.cli
  # because multi-processing library is used by the sidecar and the nanny does not like it
  # setting --no-nanny fixes this: see https://github.com/dask/distributed/issues/2142
  print_info "Starting as a dask worker ${DASK_WORKER_VERSION} -> ${DASK_SCHEDULER_URL} ..."
  print_info "Worker resources set as: $resources"
  if [ "${SC_BOOT_MODE}" = "debug" ]; then
    exec watchmedo auto-restart --recursive --pattern="*.py;*/src/*" --ignore-patterns="*test*;pytest_simcore/*;setup.py;*ignore*" --ignore-directories -- \
      dask worker "${DASK_SCHEDULER_URL}" \
      --local-directory /tmp/dask-sidecar \
      --preload simcore_service_dask_sidecar.worker \
      --nworkers "${DASK_NPROCS}" \
      --nthreads "${DASK_NTHREADS}" \
      --dashboard-address 8787 \
      --memory-limit "${DASK_MEMORY_LIMIT}" \
      --resources "$resources" \
      --name "${DASK_WORKER_NAME}"
  elif [ "${MEMRAY_ON}" = "True" ]; then
    # memray options MUST precede '-m dask', otherwise they are passed to dask
    set -- run
    if is_true "${DASK_SIDECAR_MEMRAY_NATIVE:-True}"; then
      set -- "$@" --native
    fi
    if [ "${MEMRAY_MODE}" = "live" ]; then
      print_info "memray live tracking (main process only): run 'memray live ${MEMRAY_PORT}' ..."
      set -- "$@" --live-remote --live-port "${MEMRAY_PORT}"
    else
      mkdir -p "${MEMRAY_OUTPUT_DIR}"
      MEMRAY_OUTPUT="${MEMRAY_OUTPUT_DIR}/dask-sidecar.$(date +%Y%m%dT%H%M%SZ).${$}.bin"
      print_info "memray writing captures (worker processes included) to ${MEMRAY_OUTPUT}.* ..."
      set -- "$@" --force --follow-fork --output "${MEMRAY_OUTPUT}"
    fi
    exec memray "$@" -m dask worker "${DASK_SCHEDULER_URL}" \
      --local-directory /tmp/dask-sidecar \
      --preload simcore_service_dask_sidecar.worker \
      --nworkers "${DASK_NPROCS}" \
      --nthreads "${DASK_NTHREADS}" \
      --dashboard-address 8787 \
      --memory-limit "${DASK_MEMORY_LIMIT}" \
      --resources "$resources" \
      --name "${DASK_WORKER_NAME}"
  else
    exec dask worker "${DASK_SCHEDULER_URL}" \
      --local-directory /tmp/dask-sidecar \
      --preload simcore_service_dask_sidecar.worker \
      --nworkers "${DASK_NPROCS}" \
      --nthreads "${DASK_NTHREADS}" \
      --dashboard-address 8787 \
      --memory-limit "${DASK_MEMORY_LIMIT}" \
      --resources "$resources" \
      --name "${DASK_WORKER_NAME}"
  fi
fi
