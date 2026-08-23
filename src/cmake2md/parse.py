"""Extraction of documented functions, macros and commands from CMake sources."""

import abc
import dataclasses
import pathlib
import re
import textwrap
from collections.abc import Iterator
from collections.abc import Sequence
from typing import NamedTuple

import tree_sitter_cmake as tscmake
from tree_sitter import Language
from tree_sitter import Node
from tree_sitter import Parser
from tree_sitter import Query
from tree_sitter import QueryCursor
from tree_sitter import Tree

from . import signature
from .doc_parser import ParamKind
from .errors import Cmake2mdError

CMAKE_LANGUAGE = Language(tscmake.language())
PARSER = Parser(CMAKE_LANGUAGE)
#: Definitions that carry documentation.  The two branches are one alternation
#: rather than two queries so that symbols come out in source order; the kind
#: is read back off the captured node's type.
SYMBOL_QUERY = Query(
    CMAKE_LANGUAGE,
    """
[
  (function_def
    (function_command
      (function)
      (argument_list) @arguments)
    (body)? @body
   ) @definition
  (macro_def
    (macro_command
      (macro)
      (argument_list) @arguments)
    (body)? @body
   ) @definition
]
        """,
)
#: The argument list is optional: a call without arguments — enable_testing(),
#: project() — has no argument_list node at all, and requiring one used to drop
#: such calls together with their documentation.
COMMAND_QUERY = Query(
    CMAKE_LANGUAGE,
    """
  (normal_command
    (identifier) @name
    (argument_list)? @arguments) @command
        """,
)


@dataclasses.dataclass
class File:
    filepath: str
    content: bytes
    tree: Tree

    def get_text(self, node: Node) -> str:
        return self.content[node.start_byte : node.end_byte].decode('utf-8')


@dataclasses.dataclass
class Documented(abc.ABC):
    """Something a doc comment can be attached to."""

    name: str
    comments: list[str]
    #: File line the comment block starts on; 0 when there is no comment.
    comments_line: int
    filepath: str
    line: int

    @property
    @abc.abstractmethod
    def kind(self) -> str:
        """How this entity is called in diagnostics."""

    @property
    def location(self) -> str:
        return self.location_at(0)

    def location_at(self, line: int) -> str:
        """Point at `line`, or at the definition itself when it is unknown.

        Diagnostics about a tag know the line the tag is on, which is inside
        the comment block and so above `self.line`.
        """
        # rstrip: a comment block has no name to print after its kind.
        return f'{self.filepath}:{line or self.line}: {self.kind} {self.name}'.rstrip()


@dataclasses.dataclass
class Symbol(Documented):
    type_: str
    #: The parameters the definition's own code accepts.
    signature: signature.Signature

    @property
    def kind(self) -> str:
        return self.type_


@dataclasses.dataclass
class Command(Documented):
    args: list[str]

    @property
    def kind(self) -> str:
        return 'command'


@dataclasses.dataclass
class Variable(Documented):
    """A cache entry a user can set: option() or set(... CACHE ...).

    The two commands spell the same thing differently, and a template that
    reads their raw arguments has to know the argument order of each.  This is
    that knowledge, applied once.
    """

    #: The command that created the entry, 'option' or 'set'.
    command: str
    #: The CMake cache type: BOOL, PATH, FILEPATH, STRING or INTERNAL.
    type_: str
    #: The value the entry holds unless the user overrides it.
    default: str
    #: The help string CMake itself shows for the entry, from the command.
    #: The doc comment above it, if any, is in `comments` as for anything else.
    docstring: str
    #: The values set_property(CACHE ... PROPERTY STRINGS) restricts it to.
    choices: list[str] | None = None
    #: Whether mark_as_advanced() hides it from the ordinary user, which is
    #: CMake's own way of saying an entry is not one to reach for.
    advanced: bool = False

    @property
    def kind(self) -> str:
        return 'option' if self.command == 'option' else 'cache variable'


@dataclasses.dataclass
class Block(Documented):
    """A comment block that documents nothing but itself.

    It is where a group is defined, and where anything said about the file as
    a whole belongs.
    """

    @property
    def kind(self) -> str:
        return 'comment block'


@dataclasses.dataclass
class CommentBlock:
    lines: list[str]
    #: File line the block starts on; 0 when there is no comment.
    line: int


#: '#[[', '#[=[', '#[==[' … and the ']]', ']=]' that closes each of them.
BRACKET_OPEN_RE = re.compile(r'^#\[(=*)\[')
#: CMake's own house style marks a documentation block with '.rst:' right
#: after the opening bracket; it says what the text is, not part of the text.
RST_MARKER = '.rst:'
#: The comment node types a doc comment can be written as.
COMMENT_TYPES = frozenset({'line_comment', 'bracket_comment'})


def comment_text(file: File, node: Node) -> list[str]:
    """The lines a comment node contributes, without its markers.

    A '#' line comment gives one line; a bracket comment gives the lines
    between its brackets, so that both forms reach the tag parser as the same
    kind of thing.
    """
    text = file.get_text(node)
    if node.type != 'bracket_comment':
        # CMake attaches no meaning to how many '#' a comment line opens
        # with; a Doxygen-style '##' is exactly as common as a lone '#', and
        # stripping only one would leave the other as a stray character of
        # content.
        return [text.lstrip('#')]

    opening = BRACKET_OPEN_RE.match(text)
    if opening is None:
        return [text]
    body = text[opening.end() :].removeprefix(RST_MARKER)
    body = body.removesuffix(']' + '=' * len(opening.group(1)) + ']')
    # A bracket comment usually opens and closes on lines of its own, and
    # those lines are punctuation rather than content.  CMake's house style
    # closes with '#]==]', whose '#' is inside the comment but is plainly
    # part of the marker.  splitlines() rather than split('\n'): the source
    # may have CRLF line endings, and split('\n') would leave a stray '\r' on
    # every line but the last.
    lines = body.splitlines()
    if lines and not lines[0].strip():
        lines.pop(0)
    if lines and lines[-1].strip() in ('', '#'):
        lines.pop()
    return lines


def newlines_between(file: File, first: Node, second: Node) -> int:
    return file.content.count(b'\n', first.end_byte, second.start_byte)


def comment_block(file: File, comments: Sequence[Node]) -> CommentBlock:
    """Build a block out of consecutive comment nodes.

    The run is dedented as one block rather than line by line, which keeps
    indentation *within* the comment — nested lists, code blocks — intact.
    """
    if not comments:
        return CommentBlock(lines=[], line=0)
    text = '\n'.join(
        line for comment in comments for line in comment_text(file, comment)
    )
    return CommentBlock(
        lines=textwrap.dedent(text).split('\n'),
        line=comments[0].start_point.row + 1,
    )


def get_comments(file: File, node: Node) -> CommentBlock:
    """Collect the run of comment lines immediately above `node`.

    A blank line ends the run, so an unrelated comment further up the file is
    not absorbed into this symbol's documentation.
    """
    comments = []

    current = node
    prev = current.prev_sibling
    while prev is not None and prev.type in COMMENT_TYPES:
        if newlines_between(file, prev, current) > 1:
            break
        comments.append(prev)
        current = prev
        prev = current.prev_sibling
        # A bracket comment is a block in itself; nothing above it joins on.
        if comments[-1].type == 'bracket_comment':
            break

    comments.reverse()
    return comment_block(file, comments)


def standalone_blocks(file: File, node: Node) -> Iterator[CommentBlock]:
    """The comment blocks below `node` that document nothing.

    A block that sits directly above a definition or a call belongs to it and
    `get_comments` has it already; one separated by a blank line, or with
    nothing after it at all, stands on its own and can only be talking about
    the file or about a group.
    """
    run: list[Node] = []
    for child in node.children:
        if child.type in COMMENT_TYPES:
            if run and newlines_between(file, run[-1], child) > 1:
                yield comment_block(file, run)
                run = []
            run.append(child)
            continue

        if run:
            attached = newlines_between(file, run[-1], child) <= 1
            if not attached:
                yield comment_block(file, run)
            run = []
        yield from standalone_blocks(file, child)

    if run:
        yield comment_block(file, run)


def argument_name(file: File, argument: Node) -> str:
    """Read an argument as a name, quoted or not.

    function("foo") is legal CMake, and the quotes are not part of the name.
    The grammar already separates them out, so take the text the quotes wrap
    rather than stripping characters back off.
    """
    child = argument.children[0] if argument.children else None
    if child is not None and child.type == 'quoted_argument':
        # An empty "" has no quoted_element between its quotes.
        elements = [c for c in child.children if c.type == 'quoted_element']
        return file.get_text(elements[0]) if elements else ''
    return file.get_text(argument)


def arguments_of(file: File, argument_list: Node | None) -> list[Node]:
    """The `argument` children of an argument list, if it has one at all.

    Filtered by type: an argument list may also contain comments, which are
    not arguments.
    """
    if argument_list is None:
        return []
    return [child for child in argument_list.children if child.type == 'argument']


#: The command whose arguments declare the keywords a definition accepts.
PARSE_ARGUMENTS_COMMAND = 'cmake_parse_arguments'
#: The kinds cmake_parse_arguments() declares, in the order it takes them.
KEYWORD_KINDS = (
    ParamKind.Option,
    ParamKind.SingleArgParam,
    ParamKind.MultiArgParam,
)
#: Node types that open a scope of their own.
DEFINITION_TYPES = frozenset({'function_def', 'macro_def'})
#: The keyword that makes a set() write into the caller's scope.
PARENT_SCOPE = 'PARENT_SCOPE'
#: return(PROPAGATE VAR...) does the same, since CMake 3.25.
PROPAGATE = 'PROPAGATE'


def argument_list_of(node: Node) -> Node | None:
    return next((c for c in node.children if c.type == 'argument_list'), None)


def commands_in(node: Node) -> Iterator[Node]:
    """Every command call below `node`, excluding nested definitions.

    A function() defined inside another one parses its own arguments, and
    those say nothing about the definition that encloses it.
    """
    for child in node.children:
        if child.type in DEFINITION_TYPES:
            continue
        if child.type == 'normal_command':
            yield child
        else:
            yield from commands_in(child)


def command_name(file: File, command: Node) -> str:
    identifier = next((c for c in command.children if c.type == 'identifier'), None)
    return file.get_text(identifier) if identifier is not None else ''


def contains_variable_ref(node: Node) -> bool:
    """Whether `node` interpolates a variable, and so cannot be read as text."""
    if node.type == 'variable_ref':
        return True
    return any(contains_variable_ref(child) for child in node.children)


def keyword_list(file: File, argument: Node) -> list[str] | None:
    """Split a ';'-separated keyword list, or None if it is not literal."""
    if contains_variable_ref(argument):
        return None
    return [word for word in argument_name(file, argument).split(';') if word]


def keyword_arguments(file: File, call: Node) -> list[Node] | None:
    """The three keyword-list arguments of a cmake_parse_arguments() call.

    Both call forms are accepted; PARSE_ARGV puts two more arguments in front.
    A call too short to hold all three lists is malformed CMake, and tells us
    nothing.
    """
    arguments = arguments_of(file, argument_list_of(call))
    if not arguments:
        return None
    start = 3 if argument_name(file, arguments[0]) == 'PARSE_ARGV' else 1
    lists = arguments[start : start + len(KEYWORD_KINDS)]
    return lists if len(lists) == len(KEYWORD_KINDS) else None


def propagated_names(file: File, command: Node) -> list[Node] | None:
    """The arguments of `command` that name a variable it writes to the caller.

    None when the command propagates nothing.  The two ways to do it are
    ``set(VAR ... PARENT_SCOPE)`` and ``return(PROPAGATE VAR...)``.
    """
    arguments = arguments_of(file, argument_list_of(command))
    if not arguments:
        return None

    name = command_name(file, command)
    if name == 'set' and argument_name(file, arguments[-1]) == PARENT_SCOPE:
        return arguments[:1]
    if name == 'return' and argument_name(file, arguments[0]) == PROPAGATE:
        return arguments[1:]
    return None


def propagated_variables(file: File, body: Node | None) -> list[str] | None:
    """The variables a definition sets in its caller's scope.

    None when the code does not say: a definition that propagates nothing may
    still hand a result back some other way — a macro simply sets the variable,
    and a function is often told the name to write to by its caller.  Which is
    also why a propagated name that is not literal makes the whole list
    unknown: it is a name we cannot read, not one that is not there.
    """
    if body is None:
        return None

    names = []
    for command in commands_in(body):
        propagated = propagated_names(file, command)
        if propagated is None:
            continue
        if any(contains_variable_ref(argument) for argument in propagated):
            return None
        names += [argument_name(file, argument) for argument in propagated]
    # Deduplicated, keeping order: one variable is often set in several
    # branches of the same if().
    return list(dict.fromkeys(names)) or None


def accepted_keywords(
    file: File, body: Node | None
) -> dict[ParamKind, list[str] | None]:
    unknown: dict[ParamKind, list[str] | None] = {kind: None for kind in KEYWORD_KINDS}
    if body is None:
        return unknown

    calls = [
        command
        for command in commands_in(body)
        if command_name(file, command) == PARSE_ARGUMENTS_COMMAND
    ]
    # More than one call: which of them shapes the documented interface is
    # anyone's guess, and guessing wrong means a wrong diagnostic.
    if len(calls) != 1:
        return unknown

    arguments = keyword_arguments(file, calls[0])
    if arguments is None:
        return unknown
    return {
        kind: keyword_list(file, argument)
        for kind, argument in zip(KEYWORD_KINDS, arguments, strict=True)
    }


def extract_signature(
    file: File, declared: Sequence[Node], body: Node | None
) -> signature.Signature:
    """Read the interface of a definition off its own code.

    `declared` are the arguments of function()/macro() after the name.  An
    empty list is reported as unknown rather than as "takes nothing": a macro
    that reads ${ARGV0} declares no argument yet still takes one.
    """
    names = [argument_name(file, argument) for argument in declared]
    return signature.Signature(
        accepts={
            ParamKind.Positional: names or None,
            **accepted_keywords(file, body),
            ParamKind.OutVar: propagated_variables(file, body),
        }
    )


def extract_symbols(file: File) -> list[Symbol]:
    """Extract every function() and macro() definition, documented or not."""
    symbols = []

    query_cursor = QueryCursor(SYMBOL_QUERY)
    matches = query_cursor.matches(file.tree.root_node)
    for _, captures in matches:
        arguments = arguments_of(file, captures['arguments'][0])
        if not arguments:
            # function() without a name: malformed, and nothing to document.
            continue

        definition = captures['definition'][0]
        block = get_comments(file, definition)
        body = captures.get('body')

        symbols.append(
            Symbol(
                name=argument_name(file, arguments[0]),
                type_=definition.type.removesuffix('_def'),
                signature=extract_signature(
                    file, arguments[1:], body[0] if body else None
                ),
                comments=block.lines,
                comments_line=block.line,
                filepath=file.filepath,
                line=definition.start_point.row + 1,
            )
        )
    return symbols


class CommandCall(NamedTuple):
    node: Node
    name: str
    arguments: list[Node]


def command_calls(file: File) -> Iterator[CommandCall]:
    """Every command call in the file, as (node, name, argument nodes)."""
    query_cursor = QueryCursor(COMMAND_QUERY)
    for _, captures in query_cursor.matches(file.tree.root_node):
        captured = captures.get('arguments')
        yield CommandCall(
            captures['command'][0],
            file.get_text(captures['name'][0]),
            arguments_of(file, captured[0] if captured else None),
        )


def extract_commands(file: File) -> list[Command]:
    commands = []

    for command, name, arguments in command_calls(file):
        block = get_comments(file, command)
        commands.append(
            Command(
                name=name,
                args=[file.get_text(argument) for argument in arguments],
                comments=block.lines,
                comments_line=block.line,
                filepath=file.filepath,
                line=command.start_point.row + 1,
            )
        )
    return commands


#: The keyword that turns a set() into a cache entry.
CACHE = 'CACHE'
#: Cache type of an option(), which the command does not spell out.
OPTION_TYPE = 'BOOL'
#: Default of an option() that was given none.
OPTION_DEFAULT = 'OFF'


class CacheFields(NamedTuple):
    type_: str
    default: str
    docstring: str


def option_fields(file: File, arguments: Sequence[Node]) -> CacheFields:
    """The type, default and help string of option(NAME "doc" [DEFAULT])."""
    default = (
        argument_name(file, arguments[2]) if len(arguments) > 2 else OPTION_DEFAULT
    )
    docstring = argument_name(file, arguments[1]) if len(arguments) > 1 else ''
    return CacheFields(OPTION_TYPE, default, docstring)


def cache_set_fields(file: File, arguments: Sequence[Node]) -> CacheFields | None:
    """The type, default and help string of set(NAME ... CACHE TYPE "doc").

    None when the call writes no cache entry, which is the ordinary set() and
    not something a user can configure.
    """
    names = [argument_name(file, argument) for argument in arguments]
    if CACHE not in names:
        return None

    cache = names.index(CACHE)
    # Everything between the name and CACHE is the value; CMake joins several
    # of them with ';' into a list, so the default reads the same way.
    default = ';'.join(names[1:cache])
    type_ = names[cache + 1] if len(names) > cache + 1 else ''
    docstring = names[cache + 2] if len(names) > cache + 2 else ''
    return CacheFields(type_, default, docstring)


def cache_choices(file: File) -> dict[str, list[str]]:
    """The value lists set with set_property(CACHE ... PROPERTY STRINGS ...).

    Only calls in the same file are seen, which is where a cache entry and the
    values it is restricted to are conventionally written together.
    """
    choices: dict[str, list[str]] = {}
    for _, name, arguments in command_calls(file):
        # set_property(CACHE <entry>... PROPERTY STRINGS <value>...)
        words = [argument_name(file, argument) for argument in arguments]
        if name != 'set_property' or words[:1] != [CACHE] or 'PROPERTY' not in words:
            continue

        property_at = words.index('PROPERTY')
        if words[property_at + 1 :][:1] != ['STRINGS']:
            continue
        # A value may itself be one ';'-separated list.
        values = [
            word for value in words[property_at + 2 :] for word in value.split(';')
        ]
        for entry in words[1:property_at]:
            choices[entry] = values
    return choices


def advanced_variables(file: File) -> set[str]:
    """The entries mark_as_advanced() hides from the ordinary user.

    Its FORCE and CLEAR keywords say how hard to insist, not what to mark, so
    they are not names.
    """
    advanced: set[str] = set()
    for _, name, arguments in command_calls(file):
        if name != 'mark_as_advanced':
            continue
        advanced.update(
            word
            for argument in arguments
            if not contains_variable_ref(argument)
            for word in [argument_name(file, argument)]
            if word not in ('FORCE', 'CLEAR')
        )
    return advanced


def extract_variables(file: File) -> list[Variable]:
    """Extract the cache entries a user can set, documented or not."""
    variables = []
    choices = cache_choices(file)
    advanced = advanced_variables(file)

    for command, name, arguments in command_calls(file):
        if name not in ('option', 'set') or not arguments:
            continue
        # A computed name is nothing a reader could look up or set.
        if contains_variable_ref(arguments[0]):
            continue

        fields = (
            option_fields(file, arguments)
            if name == 'option'
            else cache_set_fields(file, arguments)
        )
        if fields is None:
            continue

        block = get_comments(file, command)
        entry = argument_name(file, arguments[0])
        variables.append(
            Variable(
                name=entry,
                command=name,
                type_=fields.type_,
                default=fields.default,
                docstring=fields.docstring,
                choices=choices.get(entry),
                advanced=entry in advanced,
                comments=block.lines,
                comments_line=block.line,
                filepath=file.filepath,
                line=command.start_point.row + 1,
            )
        )
    return variables


def extract_blocks(file: File) -> list[Block]:
    """Extract the comment blocks that document nothing but themselves."""
    return [
        Block(
            name='',
            comments=block.lines,
            comments_line=block.line,
            filepath=file.filepath,
            line=block.line,
        )
        for block in standalone_blocks(file, file.tree.root_node)
        if any(line.strip() for line in block.lines)
    ]


def parse_file(path: str | pathlib.Path) -> File:
    try:
        content = pathlib.Path(path).read_bytes()
    except OSError as exc:
        raise Cmake2mdError(f'cannot read {path}: {exc.strerror}') from exc

    # Checked once, up front, so that the per-node decoding in File.get_text
    # cannot fail later on and surface as a traceback.
    try:
        content.decode('utf-8')
    except UnicodeDecodeError as exc:
        line = content.count(b'\n', 0, exc.start) + 1
        raise Cmake2mdError(
            f'{path}:{line}: not valid UTF-8; cmake2md expects UTF-8 sources'
        ) from exc

    return File(filepath=str(path), content=content, tree=PARSER.parse(content))
