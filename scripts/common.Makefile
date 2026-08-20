# SHIM: content moved to scripts/makefiles/common.mk (naming convention: .mk = library).
# Kept so existing `include .../scripts/common.Makefile` references keep working.
# SEE scripts/makefiles/README.md
include $(dir $(lastword $(MAKEFILE_LIST)))makefiles/common.mk
