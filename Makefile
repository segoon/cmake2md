VENV ?= .venv
VENV_PYTHON := $(VENV)/bin/python

# Development happens in the venv; fall back to the system interpreter so that
# `make venv` (and a `PYTHON=... make` override) still work without one.
PYTHON ?= $(if $(wildcard $(VENV_PYTHON)),$(VENV_PYTHON),python3)

# One example per output flavour, each a self-contained project under
# examples/.  Only the template and the output extension differ, so the two
# rules below are shared and these variables say what changes.  rest/ names a
# built-in template rather than a file of its own, which is what it exists to
# show.
EXAMPLES := md rest sphinx

TEMPLATE_md := examples/md/reference.md.jinja
TEMPLATE_rest := reference.rst.jinja
TEMPLATE_sphinx := examples/sphinx/reference.rst.jinja

OUTPUT_md := examples/md/reference.md
OUTPUT_rest := examples/rest/reference.rst
OUTPUT_sphinx := examples/sphinx/reference.rst

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
example: $(addprefix example-,$(EXAMPLES)) ## Regenerate the example documentation

.PHONY: example-check
example-check: $(addprefix example-check-,$(EXAMPLES)) ## Verify the example documentation is up to date

# Static pattern rules rather than plain ones: an implicit rule is never tried
# for a .PHONY target, and these have no file behind them.
.PHONY: $(addprefix example-,$(EXAMPLES)) $(addprefix example-check-,$(EXAMPLES))

$(addprefix example-,$(EXAMPLES)): example-%:
	$(PYTHON) -m cmake2md \
		--template $(TEMPLATE_$*) \
		--output $(OUTPUT_$*) \
		examples/$*/CMakeLists.txt

$(addprefix example-check-,$(EXAMPLES)): example-check-%:
	$(PYTHON) -m cmake2md --check \
		--template $(TEMPLATE_$*) \
		--output $(OUTPUT_$*) \
		examples/$*/CMakeLists.txt

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
