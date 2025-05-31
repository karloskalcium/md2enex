# Makefile for md2enex
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
UV := $(shell command -v uv 2> /dev/null)

# cribbed from https://github.com/mozilla-services/telescope/blob/main/Makefile
.PHONY: help
help:  ## Prints out documentation for available commands
	@echo "Please use 'make <target>' where <target> is one of the following commands."
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' Makefile | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
	@echo "Check the Makefile to know exactly what each target is doing."

install: $(INSTALL_STAMP)  ## Install dependencies
$(INSTALL_STAMP): pyproject.toml uv.lock
	@echo "$(UV)"
	@if [[ -z "$(UV)" ]]; then echo "uv could not be found. See https://docs.astral.sh/uv/"; exit 2; fi
	"$(UV)" --version
	"$(UV)" sync
	touch $(INSTALL_STAMP)

.PHONY: test
test: $(INSTALL_STAMP) lint unit-test  ## Runs all linting and unit tests

.PHONY: unit-test
unit-test: $(INSTALL_STAMP)  ## Runs python unit tests
	"$(UV)" run pytest --cov --cov-report term --cov-report html

.PHONY: lint
lint: $(INSTALL_STAMP)  ## Analyze code base
	"$(UV)" run ruff check
	"$(UV)" run ruff format --check

.PHONY: format
format: $(INSTALL_STAMP)  ## Format code base
	"$(UV)" run ruff check --fix
	"$(UV)" run ruff format

.PHONY: clean
clean:  ## Delete any directories, files or logs that are auto-generated
	find . -type d -name "__pycache__" | xargs rm -rf {};
	rm -f .install.stamp .coverage
	rm -rf results dist .ruff_cache .pytest_cache export.enex

.PHONY: deepclean
deepclean: clean  ## Clean all temp files and empty UV caches and virtual environments
	rm -rf .venv/
	"$(UV)" cache clean
	"$(UV)" cache prune
	@echo UV cache and virtual environments were cleaned.
