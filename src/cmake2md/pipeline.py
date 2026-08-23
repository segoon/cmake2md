"""Turning parsed CMake sources into the enriched context a template renders.

Attaches the parsed doc comment to each symbol, command and variable, and
runs the diagnostics checking those comments against the code and against
each other.
"""

import dataclasses
import sys
from collections.abc import Mapping
from collections.abc import Sequence
from typing import Any

import jinja2

from . import checks
from . import doc_parser
from . import parse
from . import tag_lexer
from .errors import ParseError


def report(
    item: parse.Documented,
    warnings: Sequence[doc_parser.DocWarning],
    strict: bool,
) -> None:
    """Print each warning, or fail on the first one under --strict."""
    for warning in warnings:
        location = item.location_at(warning.line)
        if strict:
            raise ParseError(warning.message, location)
        print(f'{location}: warning: {warning.message}', file=sys.stderr)


@dataclasses.dataclass(frozen=True)
class DocRules:
    """How a doc comment is read: the vocabulary, and how loudly to complain."""

    specs: Mapping[str, doc_parser.TagSpec]
    strict: bool


def check_and_report(
    item: parse.Documented,
    doc: doc_parser.DocComment,
    groups: frozenset[str],
    rules: DocRules,
    reported: set[tuple[str, int]] | None,
) -> None:
    """Report where `doc` disagrees with the code, or with the groups defined.

    An `option()` or `set(... CACHE ...)` call is read twice — once as a
    `Command`, once as the `Variable` it also is — over the very same comment.
    `reported` is how the two are kept from printing every diagnostic about it
    twice: it is shared across a whole run, and a comment block is reported
    only the first time its (file, line) is seen. comments_line is 0 for an
    item with no comment at all, which carries no warnings to begin with, so
    nothing is lost by not deduplicating that.
    """
    key = (item.filepath, item.comments_line)
    if reported is None or item.comments_line == 0 or key not in reported:
        report(item, doc.warnings + checks.check(item, doc, groups), rules.strict)
        if reported is not None and item.comments_line:
            reported.add(key)


def enrich(
    item: parse.Documented,
    rules: DocRules,
    groups: frozenset[str] = frozenset(),
    reported: set[tuple[str, int]] | None = None,
    *,
    check_now: bool = True,
) -> dict[str, Any]:
    """Attach the parsed doc comment to `item`.

    `pretty` starts out as the plain description; `render_symbols` overwrites
    it for a `Symbol`, once every symbol has been enriched. A command call has
    no signature of its own for the function template to render, so its
    description is all `pretty` will ever be.

    `check_now=False` defers `check_and_report` to the caller: a standalone
    comment block is enriched before any `@defgroup` in the sources is known,
    since it is what discovers them, so an `@ingroup` inside one cannot be
    checked against the real group list until every block has been read.
    """
    try:
        doc = doc_parser.parse(
            tag_lexer.tokenize(item.comments),
            strict=rules.strict,
            first_line=item.comments_line or item.line,
            specs=rules.specs,
        )
    except ParseError as exc:
        raise exc.at(item.location_at(exc.line)) from None

    if check_now:
        check_and_report(item, doc, groups, rules, reported)

    res = dataclasses.asdict(item)
    res['doc'] = doc
    res['group'] = doc.group
    res['location'] = item.location
    res['pretty'] = doc.description
    return res


def render_symbols(
    symbols: Sequence[dict[str, Any]], function_template: jinja2.Template
) -> None:
    """Fill in `pretty` for every enriched symbol, in place.

    Done only once every symbol is enriched, and given the whole list, so
    that `symbol_link` inside the function template can resolve an `@see`
    naming another symbol in the same run instead of always missing.
    """
    for symbol in symbols:
        symbol['pretty'] = function_template.render(
            {'symbol': symbol, 'symbols': symbols}
        ).strip()


def report_undocumented(symbols: Sequence[dict[str, Any]]) -> bool:
    """Report every public symbol that carries no doc comment.

    A leading underscore is CMake's way of saying a function is private, and
    @internal says it outright; neither is required to be documented.
    """
    ok = True
    for symbol in symbols:
        if symbol['name'].startswith('_') or symbol['doc'].internal:
            continue
        if any(line.strip() for line in symbol['comments']):
            continue
        print(f'{symbol["location"]}: error: undocumented', file=sys.stderr)
        ok = False
    return ok


def collect_groups(blocks: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Build the group list out of the @defgroup tags in `blocks`.

    The order is the order they were written in, which is the only ordering
    the author gave and the one a table of contents wants. A name given to
    more than one @defgroup is a warning rather than a second entry: nothing
    would tell a reader which of the two definitions a symbol in that group
    belongs under.
    """
    groups = []
    first_seen: dict[str, str] = {}
    for block in blocks:
        doc = block['doc']
        for section in doc.of_kind(doc_parser.DEFGROUP):
            earlier = first_seen.setdefault(section.name, block['location'])
            if earlier != block['location']:
                print(
                    f'{block["location"]}: warning: @defgroup {section.name} '
                    f'is already defined at {earlier}',
                    file=sys.stderr,
                )
                continue
            groups.append(
                {
                    'name': section.name,
                    # A group with no title reads by its own name.
                    'title': section.text or section.name,
                    'description': doc.description,
                    'doc': doc,
                    'location': block['location'],
                }
            )
    return groups


def warn_duplicate_symbols(symbols: Sequence[parse.Symbol]) -> None:
    """Report a name defined more than once across the sources read.

    CMake allows the redefinition, so this is a warning: the documentation
    would otherwise describe the same name twice with no hint of which
    definition wins.
    """
    first_seen: dict[str, parse.Symbol] = {}
    for symbol in symbols:
        earlier = first_seen.setdefault(symbol.name, symbol)
        if earlier is not symbol:
            print(
                f'{symbol.location}: warning: {symbol.name} is already '
                f'defined at {earlier.location}',
                file=sys.stderr,
            )
