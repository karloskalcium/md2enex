# Makefile for wtf-bot
# Tested with GNU Make 3.8.1
MAKEFLAGS += --warn-undefined-variables
SHELL        	:= /usr/bin/env bash -eu

.DEFAULT_GOAL := help

# cribbed from https://marmelab.com/blog/2016/02/29/auto-documented-makefile.html and https://news.ycombinator.com/item?id=11195539
help:  ## Prints out documentation for available commands
	@awk -F ':|##' \
		'/^[^\t].+?:.*?##/ {\
			printf "\033[36m%-30s\033[0m %s\n", $$1, $$NF \
		}' $(MAKEFILE_LIST)

## Pip / Python
# Errors out if VIRTUAL_ENV is not defined and we aren't in a CI environment.
.PHONY: check-env
check-env:
ifndef POETRY_ACTIVE
ifneq ($(CI_ARG), true)
	$(error "POETRY_ACTIVE is undefined, meaning you aren't running in a virtual environment. Fix by running: 'poetry shell'")
endif
endif

SITE_PACKAGES := $(shell pip show pip | grep '^Location' | cut -f2 -d ':')
$(SITE_PACKAGES): pyproject.toml check-env
ifeq ($(CI_ARG), true)
	@echo "Do nothing; assume python dependencies were installed already"
else
	poetry install
endif

.PHONY: pip-install
pip-install: $(SITE_PACKAGES)  ## install python packages

## Test targets
.PHONY: unit-test
unit-test: pip-install  ## Run python unit tests (not implemented yet)
	echo "Unit tests not yet implemented"
	# python -m pytest -v --cov --cov-report term --cov-report xml --cov-report html

.PHONY: flake8
flake8: pip-install 	## Run Flake8 python static style checking and linting
	@echo "flake8 comments:"
	flake8 --statistics .

.PHONY: test
test: unit-test flake8 ## Run unit tests, static analysis
	@echo "All tests passed."  # This should only be printed if all of the other targets succeed

.PHONY: clean
clean:  ## Delete any directories, files or logs that are auto-generated, except python packages
	rm -rf results
	rm -rf .pytest_cache
	rm -f .coverage

.PHONY: deepclean
deepclean: clean  ## Delete python packages and virtualenv. You must run 'make python-install' after running this.
	rm -rf ENV
	@echo virtualenvironment was deleted. Type 'deactivate' to deactivate the shims.
