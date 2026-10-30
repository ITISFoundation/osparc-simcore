#
# LOCAL KUBERNETES helpers for the kind cluster and the local helmfile charts.
#

KUBECTL_VERSION := 1.36.1
KIND_VERSION := 0.32.0
HELMFILE_VERSION := 1.1.6

# $(1) command, $(2) expected version
define verify_tool_installation
	@if ! command -v $(1) >/dev/null 2>&1; then \
		echo "'$(1)' is not installed. Install version $(2) to continue."; \
		exit 1; \
	fi
	@if ! $(1) --version | grep -q "$(2)"; then \
		echo "WARNING: installed $(1) version does not match" >&2; \
		echo "Expected $(1) version:'$(2)'. Please, update!" >&2; \
		sleep 3s; \
	fi
endef

.PHONY: _require-valid-helmfile _require-valid-kubectl _require-valid-kind

_require-valid-helmfile:
	$(call verify_tool_installation,helmfile,$(HELMFILE_VERSION))

_require-valid-kubectl:
	$(call verify_tool_installation,kubectl,$(KUBECTL_VERSION))

_require-valid-kind:
	$(call verify_tool_installation,kind,$(KIND_VERSION))

# Listing this helper in .PHONY would stop GNU Make from applying its pattern
# rule, so leave it undeclared.
.helmfile-%: _require-valid-helmfile _require-valid-kubectl
	cd $(REPO_BASE_DIR) || exit 1; \
	set -a; source .env-devel; source k8s/.env-devel-k8s-override; set +a; \
	helmfile -f services/helmfile.local-ops.yaml.gotmpl $* && \
	helmfile -f services/helmfile.yaml.gotmpl $*
