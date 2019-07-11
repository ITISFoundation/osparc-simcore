.PHONY: all build clean help

objects = $(wildcard *.json)
outputs := $(objects:.json=-converted.yaml)

TOOL_IMAGE_NAME := json-schema-to-openapi-schema


# target: all – convert all json-schemas to open-api compatible and formats them in yaml
all: check $(outputs)

%-converted.yaml:%.json
	docker run \
		-v ${CURDIR}:/input \
		-v ${CURDIR}:/output \
		$(TOOL_IMAGE_NAME)

# target: check – Checks whether tool is installed
check:
	@docker history $(TOOL_IMAGE_NAME) 2>/dev/null \
	&& echo "$(TOOL_IMAGE_NAME) is in place" \
	|| echo "MISSING $(TOOL_IMAGE_NAME) tool. SEE "scripts/$(TOOL_IMAGE_NAME)" to build it"

# target: clean – Cleans all *-converted.yaml
clean: check
	- rm $(outputs)

# target: help – Display all callable targets
help:
	@echo
	@egrep "^\s*#\s*target\s*:\s*" [Mm]akefile \
	| sed -r "s/^\s*#\s*target\s*:\s*//g"
	@echo
