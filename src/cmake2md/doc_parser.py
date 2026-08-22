"""Turns a tag stream into a structured :class:`DocComment`.

This is the single place that knows the tag vocabulary.  To add a tag,
register it in :data:`TAG_SPECS` and handle it in ``Parser._handle_tag``.
Tags that are not registered are passed through into the description
verbatim (or rejected outright in strict mode), so prose that happens to
contain an '@' never breaks a documentation build.
"""

import dataclasses
import enum
import re
from typing import Sequence

from . import tag_lexer
from .errors import ParseError


class ParamKind(str, enum.Enum):
    """Kinds of function parameters; the values are the tag names."""

    Positional = 'arg'
    Option = 'option'
    SingleArgParam = 'param'
    MultiArgParam = 'multiparam'


@dataclasses.dataclass(frozen=True)
class TagSpec:
    #: Whether the tag is followed by a whitespace-delimited name.
    takes_name: bool


#: The recognised tag vocabulary.  Extension point: add an entry here and a
#: matching branch in ``Parser._handle_tag``.
TAG_SPECS: dict[str, TagSpec] = {
    **{kind.value: TagSpec(takes_name=True) for kind in ParamKind},
    'required': TagSpec(takes_name=False),
    'ingroup': TagSpec(takes_name=True),
}


@dataclasses.dataclass
class Param:
    kind: ParamKind
    name: str
    description: str
    required: bool


@dataclasses.dataclass
class DocComment:
    description: str
    group: str | None
    args: list[Param]
    options: list[Param]
    params: list[Param]
    multi_params: list[Param]
    #: Non-fatal problems found while parsing, reported by the CLI.
    warnings: list[str]


_NAME_RE = re.compile(r'\s*(\S+)(.*)', re.DOTALL)
_PARAM_TAGS = frozenset(kind.value for kind in ParamKind)


class Parser:
    def __init__(self, tokens: Sequence[tag_lexer.Tag | str], strict: bool) -> None:
        # Copied because _take_name pushes the unconsumed remainder back.
        self._tokens: list[tag_lexer.Tag | str] = list(tokens)
        self._pos = 0
        self._strict = strict

        self._doc_description = ''
        self._group: str | None = None
        self._params: list[Param] = []
        self._warnings: list[str] = []

        self._kind: ParamKind | None = None
        self._name = ''
        self._description = ''
        self._required = False

    def parse(self) -> DocComment:
        while self._pos < len(self._tokens):
            token = self._tokens[self._pos]
            self._pos += 1
            if isinstance(token, str):
                self._description += token
            else:
                self._handle_tag(token)
        self._finalize_param()

        def of_kind(kind: ParamKind) -> list[Param]:
            return [p for p in self._params if p.kind == kind]

        return DocComment(
            description=self._doc_description,
            group=self._group,
            args=of_kind(ParamKind.Positional),
            options=of_kind(ParamKind.Option),
            params=of_kind(ParamKind.SingleArgParam),
            multi_params=of_kind(ParamKind.MultiArgParam),
            warnings=self._warnings,
        )

    def _handle_tag(self, tag: tag_lexer.Tag) -> None:
        spec = TAG_SPECS.get(tag.name)
        if spec is None:
            self._unknown_tag(tag)
            return

        name = self._take_name(tag) if spec.takes_name else ''

        if tag.name in _PARAM_TAGS:
            self._finalize_param()
            self._kind = ParamKind(tag.name)
            self._name = name
            # A positional argument is required by definition.
            self._required = self._kind == ParamKind.Positional
        elif tag.name == 'required':
            if self._kind is None:
                raise ParseError(
                    '@required must follow one of '
                    f'{", ".join("@" + k.value for k in ParamKind)} '
                    f'(line {tag.line})'
                )
            self._required = True
        elif tag.name == 'ingroup':
            self._group = name

    def _unknown_tag(self, tag: tag_lexer.Tag) -> None:
        if self._strict:
            raise ParseError(f'unknown tag @{tag.name} (line {tag.line})')
        self._warnings.append(
            f'unknown tag @{tag.name} (line {tag.line}), '
            'kept as literal text; use @@ to write a literal "@"'
        )
        self._description += '@' + tag.name

    def _take_name(self, tag: tag_lexer.Tag) -> str:
        token = self._tokens[self._pos] if self._pos < len(self._tokens) else None
        m = _NAME_RE.match(token) if isinstance(token, str) else None
        if m is None:
            raise ParseError(f'@{tag.name} requires a name (line {tag.line})')
        self._tokens[self._pos] = m.group(2)
        return m.group(1)

    def _finalize_param(self) -> None:
        if self._kind is not None:
            self._params.append(
                Param(
                    kind=self._kind,
                    name=self._name,
                    description=self._description.strip(),
                    required=self._required,
                )
            )
        elif self._description.strip():
            self._doc_description = self._description.strip()

        self._kind = None
        self._name = ''
        self._description = ''
        self._required = False


def parse(
    tokens: Sequence[tag_lexer.Tag | str], *, strict: bool = False
) -> DocComment:
    return Parser(tokens, strict=strict).parse()
