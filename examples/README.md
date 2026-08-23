# Examples

One directory per output flavour. Each is a project of its own — its own
`CMakeLists.txt`, its own generated output — so a directory can be copied out
whole and used as a starting point.

| Directory | Shows | Template |
|-----------|-------|----------|
| [`md/`](md) | Markdown, with grouped option tables | its own `reference.md.jinja` |
| [`rest/`](rest) | reStructuredText that plain docutils parses | the built-in `reference.rst.jinja` |
| [`sphinx/`](sphinx) | reStructuredText using Sphinx's CMake domain | its own `reference.rst.jinja` |

Regenerate all three from the repository root with `make example`, or check
that they are up to date with `make example-check`.

`md/` is the fullest of the three: it exercises the parsing corners on
purpose, and its README lists them.
