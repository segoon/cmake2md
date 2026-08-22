"""Extraction of documented functions, macros and commands from CMake sources."""

import abc
import dataclasses
import pathlib
import textwrap

import tree_sitter_cmake as tscmake
from tree_sitter import Language
from tree_sitter import Node
from tree_sitter import Parser
from tree_sitter import Query
from tree_sitter import QueryCursor
from tree_sitter import Tree

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
   ) @definition
  (macro_def
    (macro_command
      (macro)
      (argument_list) @arguments)
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
        return f'{self.filepath}:{line or self.line}: {self.kind} {self.name}'


@dataclasses.dataclass
class Symbol(Documented):
    type_: str

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
class CommentBlock:
    lines: list[str]
    #: File line the block starts on; 0 when there is no comment.
    line: int


def get_comments(file: File, node: Node) -> CommentBlock:
    """Collect the run of comment lines immediately above `node`.

    A blank line ends the run, so an unrelated comment further up the file is
    not absorbed into this symbol's documentation.  The run is dedented as one
    block rather than line by line, which keeps indentation *within* the
    comment — nested lists, code blocks — intact.
    """
    comments = []

    current = node
    prev = current.prev_sibling
    while prev is not None and prev.type == 'line_comment':
        gap = file.content[prev.end_byte : current.start_byte]
        if gap.count(b'\n') > 1:
            break
        comments.append(file.get_text(prev).removeprefix('#'))
        current = prev
        prev = current.prev_sibling

    if not comments:
        return CommentBlock(lines=[], line=0)
    comments.reverse()
    # `current` walked up to the topmost comment of the run.
    return CommentBlock(
        lines=textwrap.dedent('\n'.join(comments)).split('\n'),
        line=current.start_point.row + 1,
    )


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

        symbols.append(
            Symbol(
                name=argument_name(file, arguments[0]),
                type_=definition.type.removesuffix('_def'),
                comments=block.lines,
                comments_line=block.line,
                filepath=file.filepath,
                line=definition.start_point.row + 1,
            )
        )
    return symbols


def extract_commands(file: File) -> list[Command]:
    commands = []

    query_cursor = QueryCursor(COMMAND_QUERY)
    matches = query_cursor.matches(file.tree.root_node)
    for _, captures in matches:
        command = captures['command'][0]
        captured = captures.get('arguments')
        arguments = arguments_of(file, captured[0] if captured else None)
        block = get_comments(file, command)

        commands.append(
            Command(
                name=file.get_text(captures['name'][0]),
                args=[file.get_text(argument) for argument in arguments],
                comments=block.lines,
                comments_line=block.line,
                filepath=file.filepath,
                line=command.start_point.row + 1,
            )
        )
    return commands


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
