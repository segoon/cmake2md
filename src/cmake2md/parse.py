"""Extraction of documented functions and commands from CMake sources."""

import dataclasses
import pathlib

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
FUNCTION_QUERY = Query(
    CMAKE_LANGUAGE,
    """
  (function_def
    (function_command
      (function)
      (argument_list
        (argument
          (unquoted_argument))) @arguments)
   ) @function_def
        """,
)
COMMAND_QUERY = Query(
    CMAKE_LANGUAGE,
    """
  (normal_command
    (identifier) @name
    (argument_list) @arguments) @command
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
class Symbol:
    name: str
    type_: str
    comments: list[str]
    filepath: str
    line: int

    @property
    def location(self) -> str:
        return f'{self.filepath}:{self.line}: {self.type_} {self.name}'


@dataclasses.dataclass
class Command:
    name: str
    args: list[str]
    comments: list[str]
    filepath: str
    line: int

    @property
    def location(self) -> str:
        return f'{self.filepath}:{self.line}: command {self.name}'


def get_comments(file: File, node: Node) -> list[str]:
    """Collect the run of comment lines immediately above `node`.

    A blank line ends the run, so an unrelated comment further up the file
    is not absorbed into the documentation of this symbol.
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
    return list(reversed(comments))


def extract_functions(file: File) -> list[Symbol]:
    symbols = []

    query_cursor = QueryCursor(FUNCTION_QUERY)
    matches = query_cursor.matches(file.tree.root_node)
    for _, captures in matches:
        argument_list = captures['arguments'][0]
        function = argument_list.children[0]

        function_def = captures['function_def'][0]

        symbols.append(
            Symbol(
                name=file.get_text(function),
                type_='function',
                comments=get_comments(file, function_def),
                filepath=file.filepath,
                line=function_def.start_point.row + 1,
            )
        )
    return symbols


def extract_commands(file: File) -> list[Command]:
    commands = []

    query_cursor = QueryCursor(COMMAND_QUERY)
    matches = query_cursor.matches(file.tree.root_node)
    for _, captures in matches:
        command = captures['command'][0]
        arguments = captures['arguments'][0]

        commands.append(
            Command(
                name=file.get_text(captures['name'][0]),
                args=[file.get_text(child) for child in arguments.children],
                comments=get_comments(file, command),
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
    return File(filepath=str(path), content=content, tree=PARSER.parse(content))
