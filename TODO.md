# TODO

Ordered roadmap. The rationale, and the comparison with the documentation
generators of other languages that produced it, are in the plan this list came
from; the short version is that cmake2md derives nothing from the code and
hands templates raw argument lists, which is where every comparable tool
(CMinx, terraform-docs, helm-docs, Doxygen, rustdoc) was ahead of it.

## Redundancy and duplication

* The context entry is `dict[str, Any]` throughout `cli`, `rendering` and
  `serialize`, which is the `Any` the project's own rules rule out. A small
  dataclass with an `asdict()` would type the whole render path.

## Smaller things

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
