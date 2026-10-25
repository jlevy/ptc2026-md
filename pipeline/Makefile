.DEFAULT_GOAL := default
UV_CONFIG_FILE := $(CURDIR)/uv.toml
export UV_CONFIG_FILE
UV_EXCLUDE_NEWER ?= 14 days
export UV_EXCLUDE_NEWER

.PHONY: default install lint test build validate

default: install lint test
install:
	uv sync --all-groups
lint:
	uv run ruff check
	uv run basedpyright
test:
	uv run pytest
build:
	uv run ptc-kb build
validate:
	uv run ptc-kb validate
