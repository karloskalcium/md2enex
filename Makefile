# Makefile for wtf-bot
# Tested with GNU Make 3.8.1
MAKEFLAGS += --warn-undefined-variables
ifeq ($(OS),Windows_NT)
  # Because of this complexity have to be explicit about selecting bash here
  SHELL := C:\Program Files\Git\bin\bash.EXE -e -u -o pipefail
else
  SHELL := /usr/bin/env bash -e -u -o pipefail
endif
.DEFAULT_GOAL := help

INSTALL_STAMP := .install.stamp
POETRY := $(shell command -v poetry 2> /dev/null)

# cribbed from https://github.com/mozilla-services/telescope/blob/main/Makefile
.PHONY: help
help:  ## Prints out documentation for available commands
	@echo "Please use 'make <target>' where <target> is one of the following commands."
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
	@echo "Check the Makefile to know exactly what each target is doing."

install: $(INSTALL_STAMP)  ## Install dependencies
$(INSTALL_STAMP): pyproject.toml poetry.lock
	@echo "$(POETRY)"
	@if [[ -z "$(POETRY)" ]]; then echo "Poetry could not be found. See https://python-poetry.org/docs/"; exit 2; fi
	"$(POETRY)" --version
	"$(POETRY)" install
	touch $(INSTALL_STAMP)

.PHONY: test
test: $(INSTALL_STAMP) lint unit-test  ## Runs all linting and unit tests

.PHONY: unit-test
unit-test: $(INSTALL_STAMP)  ## Runs python unit tests
	"$(POETRY)" run pytest --cov --cov-report term --cov-report html

.PHONY: lint
lint: $(INSTALL_STAMP)  ## Analyze code base
	"$(POETRY)" run ruff check
	"$(POETRY)" run ruff format --check

.PHONY: format
format: $(INSTALL_STAMP)  ## Format code base
	"$(POETRY)" run ruff check --fix
	"$(POETRY)" run ruff format

.PHONY: clean
clean:  ## Delete any directories, files or logs that are auto-generated
	find . -type d -name "__pycache__" | xargs rm -rf {};
	rm -f .install.stamp .coverage
	rm -rf results dist .ruff_cache .pytest_cache export.enex

.PHONY: deepclean
deepclean: clean  ## Delete all poetry environments
	"$(POETRY)" env remove --all -n
	@echo poetry environments were deleted. Type 'deactivate' to deactivate the shims or 'exit' to exit the poetry shell.
