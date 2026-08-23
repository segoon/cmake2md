import pytest

from cmake2md import checks
from cmake2md import doc_parser
from cmake2md import parse
from cmake2md import tag_lexer


@pytest.fixture
def messages(symbols_of):
    """The check messages for the first symbol of a snippet."""

    def check_source(source):
        symbol = symbols_of(source)[0]
        doc = doc_parser.parse(tag_lexer.tokenize(symbol.comments))
        return [w.message for w in checks.check(symbol, doc)]

    return check_source


PARSED = """\
# Adds a thing.
#
# {tags}
function(add_thing)
    cmake_parse_arguments(ARG "QUIET" "TIMEOUT" "SOURCES" ${{ARGN}})
endfunction()
"""


def documented(*tags):
    return PARSED.format(tags='\n# '.join(tags))


def test_documentation_matching_the_code_is_silent(messages):
    assert (
        messages(
            documented(
                '@option QUIET be quiet',
                '@param TIMEOUT seconds',
                '@multiparam SOURCES the sources',
            )
        )
        == []
    )


def test_a_keyword_the_code_does_not_take_is_reported(messages):
    assert messages(
        documented(
            '@option QUIET q',
            '@param TIMEOUT t',
            '@multiparam SRCS s',
            '@multiparam SOURCES s',
        )
    ) == ['SRCS is documented as @multiparam but add_thing does not accept it']


def test_a_keyword_documented_as_the_wrong_kind_is_reported(messages):
    assert messages(
        documented('@option QUIET q', '@option TIMEOUT t', '@multiparam SOURCES s')
    ) == ['TIMEOUT is documented as @option but add_thing takes it as @param']


def test_an_undocumented_keyword_is_reported(messages):
    assert messages(documented('@option QUIET q')) == [
        'add_thing takes TIMEOUT but it is not documented; add @param TIMEOUT',
        'add_thing takes SOURCES but it is not documented; add @multiparam SOURCES',
    ]


def test_a_name_documented_twice_is_reported(messages):
    assert messages(
        documented(
            '@option QUIET q',
            '@option QUIET again',
            '@param TIMEOUT t',
            '@multiparam SOURCES s',
        )
    ) == ['QUIET is documented twice']


def test_an_undocumented_positional_is_reported(messages):
    assert messages(
        '# Does a thing.\n#\n# @arg NAME n\nfunction(f NAME TYPE)\nendfunction()\n'
    ) == ['f takes TYPE but it is not documented; add @arg TYPE']


RETURNING = """\
# Computes a thing.
#
# {tags}
function(compute)
    set(RESULT "42" PARENT_SCOPE)
endfunction()
"""


def test_a_documented_output_variable_the_code_does_not_set_is_reported(messages):
    assert messages(
        RETURNING.format(
            tags='@set_parent_scope RESULT r\n# @set_parent_scope MISSING m'
        )
    ) == ['MISSING is documented as @set_parent_scope but compute does not set it']


def test_an_undocumented_output_variable_is_reported(messages):
    assert messages(RETURNING.format(tags='@arg NAME n')) == [
        'compute sets RESULT but it is not documented; add @set_parent_scope RESULT'
    ]


EXAMPLE = '# Adds a thing.\n#\n# @example\n{body}function(f)\nendfunction()\n'


def example(*lines):
    return EXAMPLE.format(body=''.join(f'# {line}\n' for line in lines))


def test_an_example_that_parses_as_cmake_is_silent(messages):
    assert messages(example('f(NAME x)', 'g()')) == []


def test_an_example_that_is_not_cmake_is_reported(messages):
    assert messages(example('Call it with a name and some sources.')) == [
        'the @example does not parse as CMake; put prose or another language '
        'in a fenced code block'
    ]


def test_a_fenced_cmake_example_is_checked(messages):
    assert messages(example('```cmake', 'f(NAME', '```')) == [
        'the @example does not parse as CMake; put prose or another language '
        'in a fenced code block'
    ]


def test_a_fence_naming_another_language_is_left_alone(messages):
    assert messages(example('```sh', 'cmake -DFOO=ON ..', '```')) == []


def test_a_symbol_without_an_example_is_not_checked(messages):
    assert messages('# Just prose.\nfunction(f)\nendfunction()\n') == []


def test_a_kind_the_code_does_not_declare_is_left_alone(messages):
    # The macro takes its argument through ${ARGV0}, which declares nothing,
    # so @arg is the author's word against no evidence at all.
    assert (
        messages(
            '# Fails the build.\n#\n# @arg REASON why\n'
            'macro(fail)\n    message(FATAL_ERROR "${ARGV0}")\nendmacro()\n'
        )
        == []
    )


def test_a_documented_symbol_with_no_parameters_documented_is_still_checked(messages):
    # A comment with no parameter at all is still a comment; the blind spot
    # this used to leave was that a symbol stayed unchecked until its author
    # documented at least one parameter of it.
    assert messages('# Adds a thing.\nfunction(f NAME)\nendfunction()\n') == [
        'f takes NAME but it is not documented; add @arg NAME'
    ]


def test_a_symbol_with_no_comment_at_all_is_left_alone(symbols_of):
    # Undocumented is a separate question from drifting; that one is
    # --require-docs.
    symbol = symbols_of('function(f NAME)\nendfunction()\n')[0]
    doc = doc_parser.parse(tag_lexer.tokenize(symbol.comments))
    assert checks.check(symbol, doc) == []


def test_file_tag_on_a_symbol_is_reported(messages):
    # @file documents a comment block as a whole; on a function it would
    # silently do nothing, since the block never reaches `files`. The other
    # tags keep the parameters fully documented, to isolate this message from
    # the parameter cross-check.
    assert messages(
        documented(
            '@file',
            '@option QUIET be quiet',
            '@param TIMEOUT seconds',
            '@multiparam SOURCES the sources',
        )
    ) == [
        '@file in the documentation of add_thing documents nothing; a file '
        'is documented by a comment block of its own'
    ]


def test_file_tag_on_a_block_of_its_own_is_silent():
    doc = doc_parser.parse(tag_lexer.tokenize(['@file', 'The project itself.']))
    block = parse.Block(
        name='', comments=[], comments_line=1, filepath='CMakeLists.txt', line=1
    )
    assert checks.check(block, doc) == []


def test_commands_declare_no_parameters_of_their_own(tmp_path):
    path = tmp_path / 'CMakeLists.txt'
    path.write_text('# @param FOO f\noption(BAR "d" ON)\n', encoding='utf-8')
    command = parse.extract_commands(parse.parse_file(path))[0]
    doc = doc_parser.parse(tag_lexer.tokenize(command.comments))
    assert checks.check(command, doc) == []


def test_a_warning_points_at_the_line_of_the_offending_tag(symbols_of):
    symbol = symbols_of(
        '# Adds a thing.\n'
        '#\n'
        '# @option QUIET q\n'
        '# @param NOPE n\n'
        'function(f)\n'
        '    cmake_parse_arguments(ARG "QUIET" "" "" ${ARGN})\n'
        'endfunction()\n'
    )[0]
    doc = doc_parser.parse(
        tag_lexer.tokenize(symbol.comments), first_line=symbol.comments_line
    )
    assert [w.line for w in checks.check(symbol, doc)] == [4]
