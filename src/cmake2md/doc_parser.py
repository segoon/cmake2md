"""Turns a tag stream into a structured :class:`DocComment`.

This is the single place that knows the tag vocabulary, and it knows it as
data: :data:`TAG_SPECS` says of every tag what it attaches its result to — a
parameter, a section, a field of the comment, a field of the parameter above
it — and :class:`Parser` has one arm for each of those and no tag name of its
own.  Adding a tag is adding a row.

A doubtful '@' — an unregistered tag, or a registered one that is not
followed by something name-shaped — is left in the description as written
and reported, so that a template still has something to render.  Whether the
report is fatal is the caller's ``strict``, which the command line has on
unless ``--no-strict`` says otherwise.  A registered tag with *nothing* at
all after it stays an error either way.
"""

import dataclasses
import enum
import re
from collections.abc import Mapping
from collections.abc import Sequence

from . import tag_lexer
from .errors import ParseError


class ParamKind(str, enum.Enum):
    """Kinds of function parameters; the values are the tag names."""

    Positional = 'arg'
    Option = 'option'
    SingleArgParam = 'param'
    MultiArgParam = 'multiparam'
    #: A variable the definition sets in its caller's scope.  Not called
    #: 'return' after CMake's return(), which does something else entirely.
    OutVar = 'set_parent_scope'


class TagText(enum.Enum):
    """How much of the text after a tag belongs to the tag."""

    #: None at all: the tag is a flag, and the text around it is unaffected.
    NoText = 'none'
    #: One paragraph, ending at a blank line as Doxygen's do.  What follows
    #: the blank line goes back to the description.
    Paragraph = 'paragraph'
    #: Everything up to the next tag, so the text may span paragraphs.
    Block = 'block'


class TagTarget(enum.Enum):
    """What a tag attaches its result to."""

    #: A parameter of the definition, of the ParamKind the tag is named after.
    Param = 'param'
    #: A section of the symbol's documentation, in ``doc.sections``.
    Section = 'section'
    #: The summary, ``doc.brief``, which is a section by every other measure.
    Summary = 'summary'
    #: A field of the comment as a whole: a name, or True for a bare flag.
    DocField = 'doc_field'
    #: A field of the parameter written just above the tag, likewise.
    ParamField = 'param_field'


@dataclasses.dataclass(frozen=True)
class TagSpec:
    #: What the tag attaches to, and so which of the parser's arms handles it.
    target: TagTarget
    #: Whether the tag is followed by a whitespace-delimited name.
    takes_name: bool = False
    #: How much of the text that follows the tag belongs to it.
    text: TagText = TagText.NoText
    #: The attribute a DocField or ParamField tag writes; '' for the rest.
    field: str = ''
    #: How a template labels the section this tag opens; '' for the rest.
    label: str = ''
    #: Whether the tag only means something in a comment block that
    #: documents nothing else, as @defgroup and @file do: written above a
    #: function, macro, variable or command instead, it would attach to
    #: nothing and silently do nothing.  checks.py reports that case for
    #: every tag marked this way instead of naming each one by hand.
    block_only: bool = False


#: Tags that hold one paragraph of prose about the symbol, and how a template
#: labels each.
PROSE_TAGS = {
    'note': 'Note:',
    'warning': 'Warning:',
    'since': 'Since:',
    'todo': 'TODO:',
    'see': 'See also:',
}
#: Tags that hold a block, which a code sample needs in order to keep the
#: blank lines inside it.
BLOCK_TAGS = {'example': 'Example:'}
#: The tag whose text is the summary rather than a section of its own.
BRIEF = 'brief'
#: The tag that defines a group; its name is the group's, its text the title.
DEFGROUP = 'defgroup'
#: The tag that marks a comment block as documenting the file it is in.
FILE = 'file'

#: The recognised tag vocabulary, as data: a tag is what it attaches to, so
#: adding one is adding a row here.  ``Parser`` reads this and knows no tag
#: name of its own.
TAG_SPECS: dict[str, TagSpec] = {
    **{
        kind.value: TagSpec(TagTarget.Param, takes_name=True, text=TagText.Block)
        for kind in ParamKind
    },
    **{
        name: TagSpec(TagTarget.Section, text=TagText.Paragraph, label=label)
        for name, label in PROSE_TAGS.items()
    },
    **{
        name: TagSpec(TagTarget.Section, text=TagText.Block, label=label)
        for name, label in BLOCK_TAGS.items()
    },
    BRIEF: TagSpec(TagTarget.Summary, text=TagText.Paragraph),
    # The title runs to the next blank line, like @brief's does; the
    # paragraphs below it are the group's description, which is the
    # enclosing comment block's own.
    DEFGROUP: TagSpec(
        TagTarget.Section, takes_name=True, text=TagText.Paragraph, block_only=True
    ),
    'ingroup': TagSpec(TagTarget.DocField, takes_name=True, field='group'),
    'deprecated': TagSpec(TagTarget.DocField, field='deprecated'),
    'internal': TagSpec(TagTarget.DocField, field='internal'),
    FILE: TagSpec(TagTarget.DocField, field='documents_file', block_only=True),
    # These refine the parameter written just above them.
    'required': TagSpec(TagTarget.ParamField, field='required'),
    'type': TagSpec(TagTarget.ParamField, takes_name=True, field='type_'),
    'default': TagSpec(TagTarget.ParamField, takes_name=True, field='default'),
}


@dataclasses.dataclass
class Param:
    kind: ParamKind
    name: str
    description: str
    required: bool
    #: What the value should be, from @type; '' when unsaid.
    type_: str = ''
    #: The value used when the parameter is left out, from @default.
    default: str = ''
    #: File line the tag that introduced this parameter is on.
    line: int = 0


@dataclasses.dataclass
class Section:
    """A paragraph or block a tag attached to the symbol as a whole."""

    #: The tag that opened it, without the '@': 'note', 'example', …
    kind: str
    text: str
    #: The name the tag took, for the tags that take one; '' for the rest.
    name: str = ''
    #: File line the tag is on.
    line: int = 0
    #: How a template that has no rendering of its own for `kind` labels it.
    label: str = ''


@dataclasses.dataclass
class DocWarning:
    message: str
    #: File line the problem is on.
    line: int


@dataclasses.dataclass
class DocComment:
    description: str
    #: The @brief summary, or '' when the author wrote none.
    brief: str
    group: str | None
    #: File line the @ingroup tag is on; 0 when there is none.
    group_line: int
    args: list[Param]
    options: list[Param]
    params: list[Param]
    multi_params: list[Param]
    returns: list[Param]
    #: @note, @warning, @example and the like, in the order they were written.
    sections: list[Section]
    deprecated: bool
    #: Marked @internal: documented, but not part of the public interface.
    internal: bool
    #: Marked @file: the block documents the file it was found in.
    documents_file: bool
    #: Non-fatal problems found while parsing, reported by the CLI.
    warnings: list[DocWarning]

    def of_kind(self, kind: str) -> list[Section]:
        """The sections a given tag opened, e.g. ``doc.of_kind('note')``."""
        return [section for section in self.sections if section.kind == kind]

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


# Only [ \t], not \s: a name is looked for on the tag's own line, so a tag
# left with nothing after it but a newline is one with no name at all, rather
# than one that reaches past the line break and takes the next line's word.
_NAME_RE = re.compile(r'[ \t]*(\S+)(.*)', re.DOTALL)
# A name has to carry at least one identifier character; prose that merely
# mentions a tag ('not tagged with @ingroup, so ...') would otherwise take the
# punctuation that follows it as the name.
_PLAUSIBLE_NAME_RE = re.compile(r'[A-Za-z0-9_]')
_LITERAL_HINT = 'kept as literal text; use @@ to write a literal "@"'
_PARAM_TAG_LIST = ', '.join('@' + kind.value for kind in ParamKind)
_BLANK_LINE_RE = re.compile(r'\n[ \t]*\n')


class Parser:
    def __init__(
        self,
        tokens: Sequence[tag_lexer.Tag | str],
        strict: bool,
        first_line: int,
        specs: Mapping[str, TagSpec] = TAG_SPECS,
    ) -> None:
        # Copied because _take_name pushes the unconsumed remainder back.
        self._tokens: list[tag_lexer.Tag | str] = list(tokens)
        self._pos = 0
        self._strict = strict
        self._first_line = first_line
        self._specs = specs

        self._doc_description = ''
        self._brief = ''
        #: Whether @brief has already been read once, since '' does not tell
        #: a brief left empty apart from one never given at all.
        self._brief_given = False
        #: What the DocField tags set, by the attribute each names.
        self._fields: dict[str, str | bool] = {}
        #: Where each of those tags was written, for the diagnostics.
        self._field_lines: dict[str, int] = {}
        self._params: list[Param] = []
        self._sections: list[Section] = []
        self._warnings: list[DocWarning] = []

        # What the text being read belongs to: a parameter, a section, or —
        # when nothing is open — the symbol's own description.
        self._open: Param | Section | None = None
        #: Whether the open section is the summary rather than one of many.
        self._is_summary = False
        self._ends_at_blank_line = False
        self._text = ''

    def parse(self) -> DocComment:
        while self._pos < len(self._tokens):
            token = self._tokens[self._pos]
            self._pos += 1
            if isinstance(token, str):
                self._add_text(token)
            else:
                self._handle_tag(token)
        self._close()

        def of_kind(kind: ParamKind) -> list[Param]:
            return [p for p in self._params if p.kind == kind]

        def flag(field: str) -> bool:
            return bool(self._fields.get(field, False))

        group = self._fields.get('group')
        return DocComment(
            description=self._doc_description,
            brief=self._brief,
            group=group if isinstance(group, str) else None,
            group_line=self._field_lines.get('group', 0),
            args=of_kind(ParamKind.Positional),
            options=of_kind(ParamKind.Option),
            params=of_kind(ParamKind.SingleArgParam),
            multi_params=of_kind(ParamKind.MultiArgParam),
            returns=of_kind(ParamKind.OutVar),
            sections=self._sections,
            deprecated=flag('deprecated'),
            internal=flag('internal'),
            documents_file=flag('documents_file'),
            warnings=self._warnings,
        )

    def _add_text(self, text: str) -> None:
        """Add `text` to whatever is open, ending a paragraph if it ends."""
        if self._ends_at_blank_line:
            blank = _BLANK_LINE_RE.search(text)
            if blank is not None:
                self._text += text[: blank.start()]
                self._close()
                # What follows the blank line is prose about the symbol again.
                self._add_text(text[blank.end() :])
                return
        self._text += text

    def _file_line(self, tag: tag_lexer.Tag) -> int:
        """The line `tag` is on in the file, not within the comment block."""
        return self._first_line + tag.line - 1

    def _handle_tag(self, tag: tag_lexer.Tag) -> None:
        spec = self._specs.get(tag.name)
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

        # A tag that takes no name carries a bare True instead of one.
        value: str | bool = name if spec.takes_name else True
        match spec.target:
            case TagTarget.Param | TagTarget.Section | TagTarget.Summary:
                self._open_sink(tag, spec, name)
            case TagTarget.DocField:
                if spec.field in self._fields:
                    self._warnings.append(
                        DocWarning(
                            f'@{tag.name} is given more than once; the first is kept',
                            self._file_line(tag),
                        )
                    )
                else:
                    self._fields[spec.field] = value
                    self._field_lines[spec.field] = self._file_line(tag)
            case TagTarget.ParamField:
                if not isinstance(self._open, Param):
                    raise ParseError(
                        f'@{tag.name} must follow one of {_PARAM_TAG_LIST}',
                        line=self._file_line(tag),
                    )
                setattr(self._open, spec.field, value)

        if not spec.takes_name:
            self._eat_leading_space()

    def _open_sink(self, tag: tag_lexer.Tag, spec: TagSpec, name: str) -> None:
        """Start reading text for `tag`, closing whatever was open before."""
        self._close()
        line = self._file_line(tag)
        if spec.target is TagTarget.Param:
            kind = ParamKind(tag.name)
            self._open = Param(
                kind=kind,
                name=name,
                description='',
                # A positional argument is required by definition.
                required=kind == ParamKind.Positional,
                line=line,
            )
        else:
            self._open = Section(
                kind=tag.name, text='', name=name, line=line, label=spec.label
            )
            self._is_summary = spec.target is TagTarget.Summary
        self._ends_at_blank_line = spec.text is TagText.Paragraph

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
        self._text += '@' + tag.name

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

    def _close(self) -> None:
        """Store the text read so far with whatever it belongs to."""
        text = self._text.strip()
        if isinstance(self._open, Param):
            self._open.description = text
            self._params.append(self._open)
        elif isinstance(self._open, Section):
            self._open.text = text
            if self._is_summary:
                if self._brief_given:
                    self._warnings.append(
                        DocWarning(
                            '@brief is given more than once; the first is kept',
                            self._open.line,
                        )
                    )
                else:
                    self._brief = text
                    self._brief_given = True
            else:
                # A label-less tag (@defgroup) means something by its name
                # alone, so an empty title is not a mistake — collect_groups()
                # falls back to it. Anything rendered under a label, built-in
                # or a project's own, reads as a bare '> **Label:**' if empty.
                if not text and self._open.label:
                    self._warnings.append(
                        DocWarning(
                            f'@{self._open.kind} has nothing after it',
                            self._open.line,
                        )
                    )
                self._sections.append(self._open)
        elif text:
            # Prose can come back to the description after a paragraph tag,
            # so what is already there is kept rather than replaced.
            self._doc_description = '\n\n'.join(
                part for part in (self._doc_description, text) if part
            )

        self._open = None
        self._is_summary = False
        self._ends_at_blank_line = False
        self._text = ''


def vocabulary(custom: Mapping[str, TagSpec]) -> dict[str, TagSpec]:
    """The built-in tags together with the ones a project declared itself."""
    return {**TAG_SPECS, **custom}


def parse(
    tokens: Sequence[tag_lexer.Tag | str],
    *,
    strict: bool = False,
    first_line: int = 1,
    specs: Mapping[str, TagSpec] = TAG_SPECS,
) -> DocComment:
    """Parse `tokens`; `first_line` is the file line the comment starts on."""
    return Parser(tokens, strict=strict, first_line=first_line, specs=specs).parse()
