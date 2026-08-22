"""Turns a tag stream into a structured :class:`DocComment`.

This is the single place that knows the tag vocabulary.  To add a tag,
register it in :data:`TAG_SPECS` and handle it in ``Parser._handle_tag``.

A doubtful '@' — an unregistered tag, or a registered one that is not
followed by something name-shaped — is left in the description as written
and only warned about, so that prose mentioning a tag does not break a
documentation build.  ``--strict`` turns those warnings into errors.  A
registered tag with *nothing* at all after it stays an error either way.
"""

import dataclasses
import enum
import re
from collections.abc import Sequence

from . import tag_lexer
from .errors import ParseError


class ParamKind(str, enum.Enum):
    """Kinds of function parameters; the values are the tag names."""

    Positional = 'arg'
    Option = 'option'
    SingleArgParam = 'param'
    MultiArgParam = 'multiparam'
    #: A variable the definition sets in its caller's scope: CMake's way of
    #: returning a value, so it is documented like a parameter.
    OutVar = 'return'


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
    'deprecated': TagSpec(takes_name=False),
}


@dataclasses.dataclass
class Param:
    kind: ParamKind
    name: str
    description: str
    required: bool
    #: File line the tag that introduced this parameter is on.
    line: int = 0


@dataclasses.dataclass
class DocWarning:
    message: str
    #: File line the problem is on.
    line: int


@dataclasses.dataclass
class DocComment:
    description: str
    group: str | None
    args: list[Param]
    options: list[Param]
    params: list[Param]
    multi_params: list[Param]
    returns: list[Param]
    deprecated: bool
    #: Non-fatal problems found while parsing, reported by the CLI.
    warnings: list[DocWarning]

    def all_params(self) -> list[Param]:
        """Every documented parameter, whatever its kind, in source order."""
        return sorted(
            [
                *self.args,
                *self.options,
                *self.params,
                *self.multi_params,
                *self.returns,
            ],
            key=lambda param: param.line,
        )


_NAME_RE = re.compile(r'\s*(\S+)(.*)', re.DOTALL)
# A name has to carry at least one identifier character; prose that merely
# mentions a tag ('not tagged with @ingroup, so ...') would otherwise take the
# punctuation that follows it as the name.
_PLAUSIBLE_NAME_RE = re.compile(r'[A-Za-z0-9_]')
_PARAM_TAGS = frozenset(kind.value for kind in ParamKind)
_LITERAL_HINT = 'kept as literal text; use @@ to write a literal "@"'


class Parser:
    def __init__(
        self,
        tokens: Sequence[tag_lexer.Tag | str],
        strict: bool,
        first_line: int,
    ) -> None:
        # Copied because _take_name pushes the unconsumed remainder back.
        self._tokens: list[tag_lexer.Tag | str] = list(tokens)
        self._pos = 0
        self._strict = strict
        self._first_line = first_line

        self._doc_description = ''
        self._group: str | None = None
        self._deprecated = False
        self._params: list[Param] = []
        self._warnings: list[DocWarning] = []

        self._kind: ParamKind | None = None
        self._name = ''
        self._description = ''
        self._required = False
        self._line = 0

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
            returns=of_kind(ParamKind.OutVar),
            deprecated=self._deprecated,
            warnings=self._warnings,
        )

    def _file_line(self, tag: tag_lexer.Tag) -> int:
        """The line `tag` is on in the file, not within the comment block."""
        return self._first_line + tag.line - 1

    def _handle_tag(self, tag: tag_lexer.Tag) -> None:
        spec = TAG_SPECS.get(tag.name)
        if spec is None:
            self._literal_tag(tag, f'unknown tag @{tag.name}, {_LITERAL_HINT}')
            return

        name = ''
        if spec.takes_name:
            taken = self._take_name(tag)
            if taken is None:
                self._literal_tag(
                    tag,
                    f'@{tag.name} is not followed by a name, {_LITERAL_HINT}',
                )
                return
            name = taken

        if tag.name in _PARAM_TAGS:
            self._finalize_param()
            self._kind = ParamKind(tag.name)
            self._name = name
            self._line = self._file_line(tag)
            # A positional argument is required by definition.
            self._required = self._kind == ParamKind.Positional
        elif tag.name == 'required':
            if self._kind is None:
                raise ParseError(
                    '@required must follow one of '
                    f'{", ".join("@" + k.value for k in ParamKind)}',
                    line=self._file_line(tag),
                )
            self._required = True
        elif tag.name == 'ingroup':
            self._group = name
        elif tag.name == 'deprecated':
            # Symbol-level: a parameter cannot be deprecated on its own.
            self._deprecated = True

        if not spec.takes_name:
            self._eat_leading_space()

    def _eat_leading_space(self) -> None:
        """Drop the space that separated a valueless tag from the text.

        The space before the tag stays in the description; without this the
        one after it would remain as well, doubling it.
        """
        token = self._tokens[self._pos] if self._pos < len(self._tokens) else None
        if isinstance(token, str) and token.startswith(' '):
            self._tokens[self._pos] = token[1:]

    def _literal_tag(self, tag: tag_lexer.Tag, message: str) -> None:
        """Keep `tag` in the text as written, saying why (or fail if strict)."""
        if self._strict:
            raise ParseError(message, line=self._file_line(tag))
        self._warnings.append(DocWarning(message, self._file_line(tag)))
        self._description += '@' + tag.name

    def _take_name(self, tag: tag_lexer.Tag) -> str | None:
        """Consume the word after `tag`, or return None if it is not a name.

        Nothing is consumed in the None case, so the caller can fall back to
        treating the tag as literal text.  A tag with no text after it at all
        raises instead: there is nothing the author could have meant.
        """
        token = self._tokens[self._pos] if self._pos < len(self._tokens) else None
        m = _NAME_RE.match(token) if isinstance(token, str) else None
        if m is None:
            raise ParseError(f'@{tag.name} requires a name', line=self._file_line(tag))
        name = m.group(1)
        if not _PLAUSIBLE_NAME_RE.search(name):
            return None
        self._tokens[self._pos] = m.group(2)
        return name

    def _finalize_param(self) -> None:
        if self._kind is not None:
            self._params.append(
                Param(
                    kind=self._kind,
                    name=self._name,
                    description=self._description.strip(),
                    required=self._required,
                    line=self._line,
                )
            )
        elif self._description.strip():
            self._doc_description = self._description.strip()

        self._kind = None
        self._name = ''
        self._description = ''
        self._required = False
        self._line = 0


def parse(
    tokens: Sequence[tag_lexer.Tag | str],
    *,
    strict: bool = False,
    first_line: int = 1,
) -> DocComment:
    """Parse `tokens`; `first_line` is the file line the comment starts on."""
    return Parser(tokens, strict=strict, first_line=first_line).parse()
