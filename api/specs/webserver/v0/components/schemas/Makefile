.PHONY: all build clean help

objects = $(wildcard *.json)
outputs := $(objects:.json=-converted.yaml)

# target: all – convert all json-schemas to open-api compatible and formats them in yaml
all: $(outputs)

### target: build – Builds tool
## TODO: Add in ITIS/Dockerfile and execute as host user!
## build:
##	docker build -t json2openapiconverter .

%-converted.yaml:%.json
	docker run -v ${CURDIR}:/input -v ${CURDIR}:/output json2openapiconverter

# target: clean – Cleans all *-converted.yaml
clean:
	- rm $(outputs)

# target: help – Display all callable targets
help:
	@echo
	@egrep "^\s*#\s*target\s*:\s*" [Mm]akefile \
	| sed -r "s/^\s*#\s*target\s*:\s*//g"
	@echo
