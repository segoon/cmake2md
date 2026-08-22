import pytest

from cmake2md import parse
from cmake2md.errors import Cmake2mdError


@pytest.fixture
def symbols(cmake_file):
    return parse.extract_symbols(parse.parse_file(cmake_file))


def test_extract_symbols_finds_functions_and_macros_in_source_order(symbols):
    assert [(s.name, s.type_) for s in symbols] == [
        ('example_add_library', 'function'),
        ('undocumented_function', 'function'),
        ('example_warn', 'macro'),
    ]


def test_symbols_carry_their_location(symbols, cmake_file):
    symbol = symbols[0]
    assert symbol.filepath == str(cmake_file)
    assert symbol.line > 0
    assert 'example_add_library' in symbol.location


def test_doc_comment_is_attached_to_the_symbol(symbols):
    text = '\n'.join(symbols[0].comments)
    assert 'Adds a library.' in text
    assert '@arg NAME the target name' in text


def test_undocumented_function_has_no_comments(symbols):
    by_name = {s.name: s for s in symbols}
    assert by_name['undocumented_function'].comments == []


def test_comment_block_is_dedented_but_keeps_relative_indentation(tmp_path):
    source = tmp_path / 'CMakeLists.txt'
    source.write_text(
        '# Steps:\n#   - first\n#     details\nfunction(f)\nendfunction()\n',
        encoding='utf-8',
    )
    file = parse.parse_file(source)
    assert parse.extract_symbols(file)[0].comments == [
        'Steps:',
        '  - first',
        '    details',
    ]


def test_comment_block_without_a_common_indent_is_left_alone(tmp_path):
    source = tmp_path / 'CMakeLists.txt'
    source.write_text(
        '#no space\n# spaced\nfunction(f)\nendfunction()\n', encoding='utf-8'
    )
    file = parse.parse_file(source)
    assert parse.extract_symbols(file)[0].comments == ['no space', ' spaced']


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


def test_non_utf8_file_is_reported_with_its_line(tmp_path):
    source = tmp_path / 'CMakeLists.txt'
    source.write_bytes(
        '# ok\n# caf\xe9\nfunction(f)\nendfunction()\n'.encode('latin-1')
    )
    with pytest.raises(Cmake2mdError, match='CMakeLists.txt:2: not valid UTF-8'):
        parse.parse_file(source)
