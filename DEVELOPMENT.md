# Developing cmake2md

```shell
make install    # pip install -e '.[dev]'
make check      # lint, type check and test, as CI does
```

`make help` lists the rest: `test`, `lint`, `format`, `typecheck`, `example`
(regenerate `examples/reference.md`), `dist`, `clean` and, for maintainers,
`release-check`, `publish-test` and `publish`.

Every pull request runs `make check example-check` on Linux, the test suite on
Linux, macOS and Windows for each supported Python version, and a packaging
smoke test. The `ci-ok` job summarises all of them; it is the single check to
require in the branch protection rule, so that changing the test matrix never
means editing that rule.

## How it fits together

Each module has one job, and they stack:

| Module | Job |
|--------|-----|
| `parse.py` | Reads CMake with tree-sitter: symbols, commands, cache variables, comment blocks, and what a definition's own code accepts. |
| `tag_lexer.py` | Splits a comment into literal text and `@tags`. Knows no tag names. |
| `doc_parser.py` | Turns that stream into a `DocComment`. The single place that knows the vocabulary. |
| `signature.py` | What a definition accepts, as read from its code rather than its comment. |
| `checks.py` | Where the comment and the code disagree. |
| `rendering.py` | The Jinja environment, the template search path and the filters. |
| `serialize.py` | The same model as JSON. |
| `config.py` | The `cmake2md.toml` a project keeps beside its CMake code. |
| `cli.py` | Arguments, the passes over the sources, and writing the output. |

## Adding a tag

The vocabulary lives in `TAG_SPECS` in `src/cmake2md/doc_parser.py`, as data:
adding a tag is adding a row, and `Parser` names no tag of its own.

A `TagSpec` says three things. **What the tag attaches to**, `TagTarget`:

| Target | The tag becomes | Example |
|--------|-----------------|---------|
| `Param` | a parameter, of the `ParamKind` the tag is named after | `@option` |
| `Section` | an entry in `doc.sections`, found by `doc.of_kind()` | `@note` |
| `Summary` | `doc.brief`, a section by every other measure | `@brief` |
| `DocField` | the `field` of the comment as a whole | `@ingroup`, `@internal` |
| `ParamField` | the `field` of the parameter written above it | `@required`, `@type` |

**Whether it takes a name**, `takes_name` — a `DocField` or `ParamField` tag
that takes one stores it, and one that does not stores `True`, which is what
makes `@ingroup build` and `@internal` the same kind of thing. And **how much
of the following text is its own**, `TagText`: `Paragraph` ends at a blank line
as Doxygen's tags do, `Block` runs to the next tag so a code sample keeps its
blank lines, and `NoText` leaves the text where it was.

So a new prose tag is one row:

```python
'author': TagSpec(TagTarget.Section, text=TagText.Paragraph, label='Author:'),
```

A new parameter *kind* is the one genuinely large addition: it also needs
`signature.py` to read it out of the code and `checks.py` to compare the two.

A project that wants a tag of its own does not need any of this — it declares
it in the `[tags]` table of `cmake2md.toml`, which builds the same `TagSpec`.

## Two rules the code keeps

**Never warn wrongly.** Everything read out of the CMake source is either known
exactly or not at all. A keyword list built from a variable, two
`cmake_parse_arguments()` calls in one body, a macro reaching for `${ARGV0}`,
an output variable whose name the caller supplies: each leaves the matching
part of the signature `None`, and nothing about it is ever reported. A warning
cmake2md prints is a real disagreement, so nobody has to learn to ignore them.

**Nothing disappears silently.** A symbol whose group has no `@defgroup`
behind it still gets rendered, under a heading of its own; a tag that is not
recognised is left in the text and reported rather than swallowed.
