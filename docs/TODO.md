# TODO

## Redundancy and duplication

* The context entry is `dict[str, Any]` throughout `cli`, `rendering` and
  `serialize`, which is the `Any` the project's own rules rule out. A small
  dataclass with an `asdict()` would type the whole render path.

## From the CMinx comparison

Candidates, not decisions — raised by comparing cmake2md with
[CMinx](https://github.com/CMakePP/CMinx), the other CMake documentation
generator. Sphinx output and `include()` following came up too and stay
decided against, below.

* The checking pass is silent where the code is not plain enough to read: a
  keyword list built from a variable, two `cmake_parse_arguments()` calls, a
  macro reaching for `${ARGV0}`. Never warning wrongly is the right rule, but
  it leaves the user unable to tell "checked and fine" from "not checked at
  all". A `--verbose` line naming the symbols left unchecked, and why, would
  make the coverage visible without weakening the rule.
* Targets and tests — `add_library()`, `add_executable()`, `add_test()` — are
  reachable only through the generic `commands` list, so a template wanting a
  table of them has to parse the raw `args` itself. CMinx treats them as
  first-class. Whether they belong in a *module* documentation tool is the
  open question.
* The prior-art table compares cmake2md with CMinx but does not say when to
  pick CMinx: a project already rendering with Sphinx should. One honest
  sentence there costs nothing and makes the rest of the table credible.

## Decided against

Recorded so they are not revisited: reStructuredText/Sphinx output (CMinx and
upstream CMake cover it), `@copydoc`, following `include()` and
`add_subdirectory()`, HTML themes, a client-side search index.
