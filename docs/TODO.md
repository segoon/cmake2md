# TODO

## From the CMinx comparison

[CMinx](https://github.com/CMakePP/CMinx), the other CMake documentation
generator.

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

## Decided against

Recorded so they are not revisited: `@copydoc`, following `include()` and
`add_subdirectory()`, HTML themes, a client-side search index.
