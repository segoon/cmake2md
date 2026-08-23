VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python

# Development happens in the venv; fall back to the system interpreter so that
# `make venv` (and a `PYTHON=... make` override) still work without one.
PYTHON ?= $(if $(wildcard $(VENV_PYTHON)),$(VENV_PYTHON),python3)

EXAMPLE_TEMPLATE := examples/reference.md.jinja
EXAMPLE_SOURCE := examples/CMakeLists.txt
EXAMPLE_OUTPUT := examples/reference.md

.DEFAULT_GOAL := help

.PHONY: help
help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

.PHONY: venv
venv: ## Create the development venv at $(VENV)
	python3 -m venv $(VENV)
	$(VENV_PYTHON) -m pip install -e '.[dev]'

.PHONY: install
install: ## Install the package and the development tools
	$(PYTHON) -m pip install -e '.[dev]'

.PHONY: test
test: ## Run the test suite
	$(PYTHON) -m pytest

.PHONY: lint
lint: ## Check for lint errors
	$(PYTHON) -m ruff check .
	$(PYTHON) -m ruff format --check .

.PHONY: format
format: ## Reformat the sources in place
	$(PYTHON) -m ruff check --fix .
	$(PYTHON) -m ruff format .

.PHONY: typecheck
typecheck: ## Run the type checker
	$(PYTHON) -m mypy

.PHONY: check
check: lint typecheck test ## Run everything CI runs

.PHONY: toc
toc: ## Regenerate the README table of contents
	npx --yes doctoc@2 --title '**Table of contents**' README.md

.PHONY: toc-check
toc-check: ## Verify the README table of contents is up to date
	@cp README.md /tmp/cmake2md-README.md.orig
	@$(MAKE) toc >/dev/null
	@if diff -q /tmp/cmake2md-README.md.orig README.md >/dev/null; then \
		rm /tmp/cmake2md-README.md.orig; \
	else \
		mv /tmp/cmake2md-README.md.orig README.md; \
		echo "README.md table of contents is out of date; run 'make toc'" >&2; \
		exit 1; \
	fi

.PHONY: example
example: ## Regenerate the example documentation
	$(PYTHON) -m cmake2md \
		--template $(EXAMPLE_TEMPLATE) \
		--output $(EXAMPLE_OUTPUT) \
		$(EXAMPLE_SOURCE)

.PHONY: example-check
example-check: ## Verify the example documentation is up to date
	$(PYTHON) -m cmake2md --check \
		--template $(EXAMPLE_TEMPLATE) \
		--output $(EXAMPLE_OUTPUT) \
		$(EXAMPLE_SOURCE)

.PHONY: dist
dist: clean ## Build the sdist and the wheel
	$(PYTHON) -m build
	$(PYTHON) -m twine check --strict dist/*

.PHONY: release-check
release-check: check example-check dist ## Everything that must pass before a release

.PHONY: publish-test
publish-test: release-check ## Upload to TestPyPI
	$(PYTHON) -m twine upload --repository testpypi dist/*

.PHONY: publish
publish: release-check ## Upload to PyPI
	$(PYTHON) -m twine upload dist/*

.PHONY: clean
clean: ## Remove build artifacts and caches
	rm -rf build dist .pytest_cache .ruff_cache .mypy_cache
	rm -rf src/*.egg-info *.egg-info
	rm -rf .venv/
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
