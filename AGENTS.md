# The product

cmake2md is a documentation generator for cmake.
It parses cmake source files, extracts doxygen-like comments,
and uses jinja templates to generate final documentation.

# Core documentation

- @README.md - the main user documentation.
- @TODO.md - the plans.

# Development

* git
* .github
* Makefile
* tests/
* examples/ - a generic example of cmake2md user

## Python

Python, mypy, ruff, pyproject.toml.

* Use annotations.
* Do not use `Any`, always set the strict direct type.

## Generic

* Do not add new external dependencies without explicit user permission.
* Be careful when wording user output. Error message must describe what's wrong
  from the user point of view instead of dumping low-level integer error codes
  (unless the error reason is unknown).
* Note that you're a consultant, not a product owner.
  Only the user may make important architectural desicions.
  If you have any ideas, remarks, suggestions, or you see extra problems with the user choise,
  you have to inform the user.
* If the implementation can be extendable for non-existing but possible features/changes,
  it should be extendable. Even if some feature is not yet planned, it might be planned soon.
* If you catch a bug in the code, write a regression test for that.
* After you add/edit a file, check the whole file for code duplication in tests. Don't leave similar boilerplate.
* When fixing a bug, search for similar bugs in the nearby code.
* When found a bug, elaborate whether it is possible to redesign the system to make such bugs impossible

- DRY, KISS, SOLID.
* Prefer SRP, avoid god objects.
* Use OOP where appropriate.

## Comments

* Code comments have to describe "why", not "how".
* Code comments must not duplicate the code, must be brief.
* Avoid obvious comments.
* Document complex/TODO/weird code briefly.

## Runtime

* Use venv at .venv
* test with `make check`
