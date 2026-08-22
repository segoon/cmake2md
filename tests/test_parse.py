import pytest

from cmake2md import parse
from cmake2md.errors import Cmake2mdError


def test_extract_functions_finds_every_function(cmake_file):
    file = parse.parse_file(cmake_file)
    symbols = parse.extract_functions(file)
    assert [s.name for s in symbols] == [
        'example_add_library',
        'undocumented_function',
    ]
    assert all(s.type_ == 'function' for s in symbols)


def test_symbols_carry_their_location(cmake_file):
    file = parse.parse_file(cmake_file)
    symbol = parse.extract_functions(file)[0]
    assert symbol.filepath == str(cmake_file)
    assert symbol.line > 0
    assert 'example_add_library' in symbol.location


def test_doc_comment_is_attached_to_the_function(cmake_file):
    file = parse.parse_file(cmake_file)
    symbol = parse.extract_functions(file)[0]
    text = '\n'.join(symbol.comments)
    assert 'Adds a library.' in text
    assert '@arg NAME the target name' in text


def test_undocumented_function_has_no_comments(cmake_file):
    file = parse.parse_file(cmake_file)
    symbols = {s.name: s for s in parse.extract_functions(file)}
    assert symbols['undocumented_function'].comments == []


def test_blank_line_terminates_a_comment_block(tmp_path):
    source = tmp_path / 'CMakeLists.txt'
    source.write_text(
        '# unrelated\n\n# the real doc\noption(FOO "d" ON)\n', encoding='utf-8'
    )
    file = parse.parse_file(source)
    command = parse.extract_commands(file)[0]
    assert [c.strip() for c in command.comments] == ['the real doc']


def test_extract_commands_keeps_raw_arguments(cmake_file):
    file = parse.parse_file(cmake_file)
    options = [c for c in parse.extract_commands(file) if c.name == 'option']
    assert [c.args[0] for c in options] == [
        'EXAMPLE_BUILD_TESTS',
        'EXAMPLE_STATIC',
    ]

    first = options[0]
    assert first.args[0] == 'EXAMPLE_BUILD_TESTS'
    assert first.args[1] == '"Build tests"'
    assert first.args[2] == 'ON'


def test_extract_commands_handles_set_with_cache(cmake_file):
    file = parse.parse_file(cmake_file)
    sets = [c for c in parse.extract_commands(file) if c.name == 'set']
    assert sets[0].args[0] == 'EXAMPLE_DIR'
    assert sets[0].args[4] == '"Where example lives"'


def test_missing_file_raises_a_friendly_error(tmp_path):
    with pytest.raises(Cmake2mdError, match='cannot read'):
        parse.parse_file(tmp_path / 'nope.txt')
