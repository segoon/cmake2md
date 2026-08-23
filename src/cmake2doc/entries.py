"""The enriched entries and rendering context: parsed CMake plus its doc
comment.

Kept separate from `pipeline`, which builds these, so that `rendering` can
import the shapes it renders without importing `pipeline` itself:
`pipeline` already depends on `checks`, and `checks` depends on `rendering`,
so a `rendering` -> `pipeline` import would be circular.
"""

import dataclasses
from typing import Protocol

from . import doc_parser
from . import parse

#: The three fields every Enriched* adds are always passed as keywords (see
#: pipeline.py's enrich_*), so kw_only=True costs nothing at a call site. It
#: is also what lets them follow parse.Variable's defaulted `choices` and
#: `advanced` without violating the dataclass no-default-before-a-default
#: field-ordering rule.  Each field below gets its own dataclasses.field()
#: call, not a shared one: dataclass() mutates a Field object's .name/.type
#: in place, so reusing one instance across attributes would corrupt all
#: but the last one's metadata.


@dataclasses.dataclass
class EnrichedSymbol(parse.Symbol):
    doc: doc_parser.DocComment = dataclasses.field(kw_only=True)
    group: str | None = dataclasses.field(kw_only=True)
    pretty: str = dataclasses.field(kw_only=True)


@dataclasses.dataclass
class EnrichedCommand(parse.Command):
    doc: doc_parser.DocComment = dataclasses.field(kw_only=True)
    group: str | None = dataclasses.field(kw_only=True)
    pretty: str = dataclasses.field(kw_only=True)


@dataclasses.dataclass
class EnrichedVariable(parse.Variable):
    doc: doc_parser.DocComment = dataclasses.field(kw_only=True)
    group: str | None = dataclasses.field(kw_only=True)
    pretty: str = dataclasses.field(kw_only=True)


@dataclasses.dataclass
class EnrichedTarget(parse.Target):
    doc: doc_parser.DocComment = dataclasses.field(kw_only=True)
    group: str | None = dataclasses.field(kw_only=True)
    pretty: str = dataclasses.field(kw_only=True)


@dataclasses.dataclass
class EnrichedBlock(parse.Block):
    doc: doc_parser.DocComment = dataclasses.field(kw_only=True)
    group: str | None = dataclasses.field(kw_only=True)
    pretty: str = dataclasses.field(kw_only=True)


class Item(Protocol):
    """What a template filter needs from one entry, regardless of kind.

    Structural rather than `EnrichedSymbol | EnrichedCommand |
    EnrichedVariable | EnrichedTarget | EnrichedBlock`: a filter like
    `documented`/`public`/`only_group` only ever touches these five fields,
    and every `Enriched*` above satisfies this automatically.
    """

    name: str
    comments: list[str]
    doc: doc_parser.DocComment
    group: str | None
    pretty: str


@dataclasses.dataclass
class Group:
    name: str
    title: str
    description: str
    doc: doc_parser.DocComment
    location: str


@dataclasses.dataclass
class Context:
    """Everything a template is rendered with."""

    symbols: list[EnrichedSymbol]
    variables: list[EnrichedVariable]
    targets: list[EnrichedTarget]
    commands: list[EnrichedCommand]
    groups: list[Group]
    files: list[EnrichedBlock]
