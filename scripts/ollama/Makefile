SCRIPTS_DIR      := $(dir $(abspath $(dir $(lastword $(MAKEFILE_LIST)))))
HELP_MK          ?= $(SCRIPTS_DIR)makefiles/help.mk
OLLAMA_MK        ?= $(SCRIPTS_DIR)makefiles/ollama.mk
OLLAMA_MODEL     := translategemma:4b

include $(HELP_MK)
include $(OLLAMA_MK)
