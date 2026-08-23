# TODO

Ordered roadmap. The rationale, and the comparison with the documentation
generators of other languages that produced it, are in the plan this list came
from; the short version is that cmake2md derives nothing from the code and
hands templates raw argument lists, which is where every comparable tool
(CMinx, terraform-docs, helm-docs, Doxygen, rustdoc) was ahead of it.

## Redundancy and duplication

* `checks._group_problems` and `_misplaced_file_tag` each name their tag
  (`DEFGROUP`, `@file`) rather than reading a `TagSpec` flag that says a tag
  belongs in a comment block of its own; a third such tag would be a third
  hand-written function rather than a row of data.
* `function.md.jinja` hardcodes `Note:`, `Warning:` and `TODO:`, and lists
  the kinds it renders by name, although `Section.label` already carries
  those strings from `PROSE_TAGS`. Adding a built-in prose tag today means
  editing the template as well as `doc_parser.py`. Render every section
  through `section.label`, keeping only the genuinely special cases
  (`example`, `since`, `see`).
* `rendered_kinds` in that template includes `brief`, which is a
  `TagTarget.Summary` and never appears in `doc.sections`.
* `parse.cache_choices` computes `words.index('PROPERTY')` twice.
* The context entry is `dict[str, Any]` throughout `cli`, `rendering` and
  `serialize`, which is the `Any` the project's own rules rule out. A small
  dataclass with an `asdict()` would type the whole render path.

## Documentation

* `function.md.jinja` says a project declares tags in `[tool.cmake2md.tags]`;
  the table is `[tags]`, as the README and `config.py` have it.
* The README says a `@defgroup` title is "the rest of the line". It is a
  paragraph: a title written over two lines is all title.
* The template-key table lists `type_` twice, once for symbols and once for
  variables, which reads as a contradiction.
* Neither the README nor `--help` says that a registered tag with nothing at
  all after it fails the run even under `--no-strict`, while `@ingroup, so …`
  is only a warning. The `doc_parser` module docstring says it; the
  user-facing documentation does not.
* The flag table gives `--no-strict` but not the affirmative `--strict`.

## Smaller things

* An empty `@note` becomes a section with no text, rendered as a bare
  `> **Note:**`. Either warn or drop it.
* `config._as_tag` turns `label = ""` into the capitalised tag name through an
  `or`, and `str.capitalize()` lowercases the rest, so `myTag` labels itself
  `Mytag:`.
* An `@ingroup` inside a standalone comment block is never validated: those
  blocks are enriched before the groups are known, with an empty set.
* `comment_text` strips exactly one `#`, so a Doxygen-style `## text` block
  keeps a stray `#`.

## Decided against

Recorded so they are not revisited: reStructuredText/Sphinx output (CMinx and
upstream CMake cover it), `@copydoc`, following `include()` and
`add_subdirectory()`, HTML themes, a client-side search index.
