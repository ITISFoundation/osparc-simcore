#
# LOCAL KUBERNETES helpers for the kind cluster and the local helmfile charts.
#

#
# Helmfile configuration
#

HELMFILE_ENV := HELM_DIFF_OUTPUT_CONTEXT=5
HELMFILE_GLOBAL_FLAGS := --environment local
HELMFILE_COMMAND_FLAGS ?=

#
# utils
#

# Check that given variables are set and all have non-empty values,
# die with an error otherwise.
#
# Params:
#   1. Variable name(s) to test.
#   2. (optional) Error message to print.
guard-%:
	@ if [ "${${*}}" = "" ]; then \
		echo "Environment variable $* not set"; \
		exit 1; \
	fi

# run_helmfile <helmfile_file> <command>
# Example: $(call run_helmfile,services/helmfile.yaml.gotmpl,lint)
define run_helmfile
    cd $(REPO_BASE_DIR) || exit 1; \
    set -a; source .env-devel; source k8s/.env-devel-k8s-override; set +a; \
    $(HELMFILE_ENV) helmfile $(HELMFILE_GLOBAL_FLAGS) -f $(1) $(2) $(HELMFILE_COMMAND_FLAGS)
endef

#
# helmfile internal
#

.helmfile-%:
	@$(MAKE) .helmfile-ops-$*
	@$(MAKE) .helmfile-simcore-$*

.helmfile-ops-%:
	@$(call run_helmfile,services/helmfile.local-ops.yaml.gotmpl,$*)

.helmfile-simcore-%:
	@$(call run_helmfile,services/helmfile.yaml.gotmpl,$*)

.PHONY: .init-swarm
.init-swarm:
	@# init docker swarm for dv2 to start. we are not going to use it
	@swarm_state=$$(docker info --format '{{.Swarm.LocalNodeState}}') || exit 1; \
	if [ "$$swarm_state" = "inactive" ]; then \
		docker swarm init --advertise-addr 127.0.0.1; \
	fi
