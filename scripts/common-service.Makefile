# SHIM: content moved to scripts/makefiles/service.mk (naming convention: .mk = library).
# Kept so existing `include .../scripts/common-service.Makefile` references keep working.
# SEE scripts/makefiles/README.md
include $(dir $(lastword $(MAKEFILE_LIST)))makefiles/service.mk
