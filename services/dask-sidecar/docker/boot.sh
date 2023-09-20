#!/bin/sh
set -o errexit
set -o nounset

IFS=$(printf '\n\t')

INFO="INFO: [$(basename "$0")] "

# BOOTING application ---------------------------------------------
echo "$INFO" "Booting in ${SC_BOOT_MODE} mode ..."
echo "  User    :$(id "$(whoami)")"
echo "  Workdir :$(pwd)"
echo "  env     :$(env)"

if [ "${SC_BUILD_TARGET}" = "development" ]; then
  echo "$INFO" "Environment :"
  printenv | sed 's/=/: /' | sed 's/^/    /' | sort
  echo "$INFO" "Python :"
  python --version | sed 's/^/    /'
  command -v python | sed 's/^/    /'
  cd services/dask-sidecar || exit 1
  pip install --no-cache-dir -r requirements/dev.txt
  cd - || exit 1
  echo "$INFO" "PIP :"
  pip list | sed 's/^/    /'
fi

# RUNNING application ----------------------------------------
#
# - If DASK_START_AS_SCHEDULER is set, then it boots as scheduler otherwise as worker
# - SEE https://docs.dask.org/en/latest/setup/cli.html
# - SEE https://stackoverflow.com/questions/3601515/how-to-check-if-a-variable-is-set-in-bash
# - FIXME: create command prefix: https://unix.stackexchange.com/questions/444946/how-can-we-run-a-command-stored-in-a-variable
#

if [ ${DASK_START_AS_SCHEDULER+x} ]; then
  scheduler_version=$(dask scheduler --version)
  mkdir --parents /home/scu/.config/dask
  dask_logging=$(printf "logging:\n  distributed: %s\n  distributed.scheduler: %s" "${LOG_LEVEL:-warning}" "${LOG_LEVEL:-warning}")
  echo "$dask_logging" >> /home/scu/.config/dask/distributed.yaml

  echo "$INFO" "Starting as dask scheduler:${scheduler_version}..."
  if [ "${SC_BOOT_MODE}" = "debug-ptvsd" ]; then
    exec watchmedo auto-restart \
        --recursive \
        --pattern="*.py;*/src/*" \
        --ignore-patterns="*test*;pytest_simcore/*;setup.py;*ignore*" \
        --ignore-directories -- \
        dask scheduler \
        --preload simcore_service_dask_sidecar.scheduler
  else
    exec dask scheduler \
    --preload simcore_service_dask_sidecar.scheduler

  fi

else
  DASK_WORKER_VERSION=$(dask worker --version)
  DASK_SCHEDULER_URL=${DASK_SCHEDULER_URL:="tcp://${DASK_SCHEDULER_HOST}:8786"}

  #
  # DASK RESOURCES DEFINITION
  #
  # Following resources are defined on a dask-sidecar for computational tasks:
  # CPU: number of CPUs available (= num of processing units - DASK_SIDECAR_NUM_NON_USABLE_CPUS)
  # GPU: number GPUs available (= num of GPUs if a nvidia-smi can be run inside a docker container)
  # RAM: amount of RAM available (= CPU/nproc * total virtual memory given by python psutil - DASK_SIDECAR_NON_USABLE_RAM)
  # VRAM: amount of VRAM available (in bytes)

  # CPUs
  num_cpus=$(($(nproc) - ${DASK_SIDECAR_NUM_NON_USABLE_CPUS:-2}))
  if [ "$num_cpus" -le 0 ]; then
    # ensure the minimal amount of cpus is 1 in case the system is a dual-core or less (CI case for instance)
    num_cpus=1
  fi

  # GPUs
  num_gpus=$(python -c "from simcore_service_dask_sidecar.utils import num_available_gpus; print(num_available_gpus());")

  # RAM (is computed similarly as the default dask-sidecar computation)
  _value=$(python -c "import psutil; print(int(psutil.virtual_memory().total * $num_cpus/$(nproc)))")
  ram=$((_value - ${DASK_SIDECAR_NON_USABLE_RAM:-0}))

  # overall resources available on the dask-sidecar (CPUs and RAM are always available)
  resources="CPU=$num_cpus,RAM=$ram"

  # add the GPUs if there are any
  if [ "$num_gpus" -gt 0 ]; then
    total_vram=$(python -c "from simcore_service_dask_sidecar.utils import video_memory; print(video_memory());")
    resources="$resources,GPU=$num_gpus,VRAM=$total_vram"
  fi


  #
  # DASK RESOURCES DEFINITION --------------------------------- END
  #
  DASK_NPROCS=${DASK_NPROCS:="1"}
  DASK_NTHREADS=${DASK_NTHREADS:="$num_cpus"}
  DASK_MEMORY_LIMIT=${DASK_MEMORY_LIMIT:="$ram"}
  DASK_WORKER_NAME=${DASK_WORKER_NAME:="dask-sidecar_$(hostname)_$(date +'%Y-%m-%d_%T')_$$"}
  #
  # 'daemonic processes are not allowed to have children' arises when running the sidecar.cli
  # because multi-processing library is used by the sidecar and the nanny does not like it
  # setting --no-nanny fixes this: see https://github.com/dask/distributed/issues/2142
  echo "$INFO" "Starting as a dask worker "${DASK_WORKER_VERSION}" -> "${DASK_SCHEDULER_URL}" ..."
  echo "$INFO" "Worker resources set as: "$resources""
  if [ "${SC_BOOT_MODE}" = "debug-ptvsd" ]; then
    exec watchmedo auto-restart --recursive --pattern="*.py;*/src/*" --ignore-patterns="*test*;pytest_simcore/*;setup.py;*ignore*" --ignore-directories -- \
      dask worker "${DASK_SCHEDULER_URL}" \
      --local-directory /tmp/dask-sidecar \
      --preload simcore_service_dask_sidecar.tasks \
      --nworkers ${DASK_NPROCS} \
      --nthreads "${DASK_NTHREADS}" \
      --dashboard-address 8787 \
      --memory-limit "${DASK_MEMORY_LIMIT}" \
      --resources "$resources" \
      --name "${DASK_WORKER_NAME}"
  else
    exec dask worker "${DASK_SCHEDULER_URL}" \
      --local-directory /tmp/dask-sidecar \
      --preload simcore_service_dask_sidecar.tasks \
      --nworkers ${DASK_NPROCS} \
      --nthreads "${DASK_NTHREADS}" \
      --dashboard-address 8787 \
      --memory-limit "${DASK_MEMORY_LIMIT}" \
      --resources "$resources" \
      --name "${DASK_WORKER_NAME}"
  fi
fi
