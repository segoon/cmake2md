# TODO

## Random thoughts

* document how `include()`/`add_subdirectory()` should be handled (list dirs explicitly)
* rename to cmake2doc

## Redundancy and duplication

* The context entry is `dict[str, Any]` throughout `cli`, `rendering` and
  `serialize`, which is the `Any` the project's own rules rule out. A small
  dataclass with an `asdict()` would type the whole render path.

## From the CMinx comparison

Candidates, not decisions — raised by comparing cmake2md with
[CMinx](https://github.com/CMakePP/CMinx), the other CMake documentation
generator. Two of the four are done: `reference.rst.jinja` ships as a built-in
and the prior-art table now says when to pick CMinx. `include()` following
came up too and stays decided against, below.

* The per-symbol template name is the constant `FUNCTION_TEMPLATE_NAME =
  'function.md.jinja'`, so `symbol.pretty` is Markdown in every run and a
  template of any other format has to lay symbols out itself — as
  `reference.rst.jinja` does, duplicating the structure of
  `function.md.jinja` in another syntax. A `--function-template` option would
  end the duplication; it also adds a knob, so it waits until a second
  non-Markdown template wants it.
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

## Decided against

Recorded so they are not revisited: `@copydoc`, following `include()` and
`add_subdirectory()`, HTML themes, a client-side search index.

reStructuredText output used to be on this list, on the grounds that CMinx and
upstream CMake cover it. It came off once the CMinx comparison made the cost
plain: cmake2md renders through Jinja, so rST is a template rather than a
backend. What is still not on the roadmap is *building* a site — no Sphinx
project, no `conf.py`, no HTML. cmake2md writes the source file; what renders
it is the project's business.
