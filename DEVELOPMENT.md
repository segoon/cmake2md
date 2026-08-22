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
| `config.py` | The `[tool.cmake2md]` table. |
| `cli.py` | Arguments, the passes over the sources, and writing the output. |

## Adding a tag

The vocabulary lives in `TAG_SPECS` in `src/cmake2md/doc_parser.py`. A tag that
only carries prose needs an entry there and nothing else:

```python
PROSE_TAGS = ('brief', 'note', 'warning', 'since', 'todo', 'see', 'mytag')
```

`TagSpec` says whether the tag takes a name, and how much of the text after it
belongs to it: `TagText.Paragraph` ends at a blank line as Doxygen's tags do,
`TagText.Block` runs to the next tag so a code sample keeps its blank lines,
and `TagText.NoText` is a flag. A tag that means something structural — a flag
to set, a name to record — also needs a branch in `Parser._handle_tag`.

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
