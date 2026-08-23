# TODO

Ordered roadmap. The rationale, and the comparison with the documentation
generators of other languages that produced it, are in the plan this list came
from; the short version is that cmake2md derives nothing from the code and
hands templates raw argument lists, which is where every comparable tool
(CMinx, terraform-docs, helm-docs, Doxygen, rustdoc) was ahead of it.

## Bugs

Found by review, each reproduced through the CLI against a green test suite;
in the order they are worth fixing, worst first. Every one of them needs a
regression test, since the suite passes today.

1. **A source named twice is parsed twice.** `collect_sources` does not
   dedupe, so `cmake2md . CMakeLists.txt` renders every symbol twice and
   warns that each is `already defined at` its own location. Dedupe by
   resolved path, keeping order.

2. **Duplicate definitions are silently overwritten.** A second `@brief` or
   `@ingroup` replaces the first with nothing said; a `@defgroup` written
   twice puts the group in `groups` twice, and `reference.md.jinja` renders
   the whole section twice. `_field_lines` already records where the first
   one was, so the warning has a line to point at. `warn_duplicate_symbols`
   is the precedent.

3. **`@file` outside a comment block of its own does nothing, quietly.** On a
   `function()` it sets `documents_file` on a `Symbol` that never reaches the
   `files` list. `checks._group_problems` reports the same mistake for
   `@defgroup`; both are "a block of its own" tags, so the rule belongs in
   `TagSpec` as data rather than as a tag name in `checks.py`.

4. **`symbol_link` never links anything in the built-in reference.**
   `function.md.jinja` resolves `@see` through `symbols | default([])`, but
   `enrich()` renders it with `{'symbol': res}` alone, so the list is always
   empty. The filter works when that template is used as a whole document and
   not when it fills `pretty` — which is the path `reference.md.jinja` takes,
   so the shipped document never cross-references. Pass the symbols into the
   per-symbol render (which means enriching in two passes), or move `@see`
   out of the per-symbol template.

5. **An I/O failure is a traceback.** `write_output` and `read_ignore_file`
   let `OSError` through: an unwritable output directory or an unreadable
   `.cmake2mdignore` prints a Python stack. `parse_file` and `config.load`
   both turn the same error into a sentence, which is the standard to meet.

6. **`check = true` in the config file cannot be turned off.** Only
   `--strict` uses `BooleanOptionalAction`, so a project that records
   `check`, `inject` or `require-docs` in `cmake2md.toml` can never override
   it for one run. The `None`-means-unsaid handling in `apply_config` already
   supports the negative forms.

7. **`--json` on its own is refused.** `validate_args` demands a
   `--template`, so a consumer that wants only the model has to invent a
   throwaway template and output. Require a template only when nothing else
   was asked for.

8. **A symbol documented without parameters is never checked.** The gate in
   `checks.check` is `doc.all_params()`, so a function whose comment is one
   `@brief` and whose body is a full `cmake_parse_arguments()` is compared
   against nothing; document a single parameter and the same function
   reports the rest at once. `--require-docs` does not catch it either,
   since the symbol does have a comment. This is the common half-documented
   case, and it falls in the blind spot between the two checks — a design
   question rather than a slip, and the README describes the current gate
   inaccurately either way (see below).

## Redundancy and duplication

* The settings are listed twice, in `cli.DEFAULTS` and in `config.KEYS`, with
  nothing keeping them in step — `json` is in one and not the other. One
  table saying of each setting its kind, its default and whether it names a
  path, read by both, would make the drift impossible.
* `checks._FENCE_RE` and `rendering._FENCE_RE` are the same Markdown fence
  written twice, once capturing and once not.
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
* The README says checking is skipped for "symbols with no doc comment at
  all". The gate is a symbol with no *parameter* documented — see bug 8.
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
