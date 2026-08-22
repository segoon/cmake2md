import pytest

from cmake2md.doc_parser import ParamKind


@pytest.fixture
def accepts(symbols_of):
    """The signature of the first symbol in a snippet, as a plain dict."""

    def signature_of(body, header='function(f)', footer='endfunction()'):
        return symbols_of(f'{header}\n{body}\n{footer}\n')[0].signature.accepts

    return signature_of


def test_keywords_come_from_cmake_parse_arguments(accepts):
    assert accepts(
        'cmake_parse_arguments(ARG "QUIET" "TIMEOUT" "SOURCES;DEPENDS" ${ARGN})'
    ) == {
        ParamKind.Positional: None,
        ParamKind.Option: ['QUIET'],
        ParamKind.SingleArgParam: ['TIMEOUT'],
        ParamKind.MultiArgParam: ['SOURCES', 'DEPENDS'],
    }


def test_parse_argv_form_is_understood(accepts):
    signature = accepts('cmake_parse_arguments(PARSE_ARGV 1 ARG "QUIET" "" "SRC")')
    assert signature[ParamKind.Option] == ['QUIET']
    assert signature[ParamKind.SingleArgParam] == []
    assert signature[ParamKind.MultiArgParam] == ['SRC']


def test_unquoted_keyword_lists_are_read_too(accepts):
    assert accepts('cmake_parse_arguments(ARG QUIET;LOUD "" "" ${ARGN})')[
        ParamKind.Option
    ] == ['QUIET', 'LOUD']


def test_a_keyword_list_built_from_a_variable_is_unknown(accepts):
    signature = accepts('cmake_parse_arguments(ARG "${_OPTIONS}" "T" "" ${ARGN})')
    assert signature[ParamKind.Option] is None
    # Only the unreadable list is unknown; the others still count.
    assert signature[ParamKind.SingleArgParam] == ['T']


def test_no_call_leaves_every_keyword_kind_unknown(accepts):
    assert accepts('message(STATUS "nothing to see")') == {
        kind: None for kind in ParamKind
    }


def test_a_call_too_short_to_hold_the_lists_is_unknown(accepts):
    assert accepts('cmake_parse_arguments(ARG "QUIET")')[ParamKind.Option] is None


def test_two_calls_are_ambiguous_and_so_unknown(accepts):
    signature = accepts(
        'cmake_parse_arguments(ARG "QUIET" "" "" ${ARGN})\n'
        'cmake_parse_arguments(OTHER "LOUD" "" "" ${ARGN})'
    )
    assert signature[ParamKind.Option] is None


def test_a_call_inside_an_if_block_is_found(accepts):
    assert accepts(
        'if(WIN32)\n    cmake_parse_arguments(ARG "QUIET" "" "" ${ARGN})\nendif()'
    )[ParamKind.Option] == ['QUIET']


def test_a_nested_definition_keeps_its_own_call(symbols_of):
    outer, inner = symbols_of(
        'function(outer)\n'
        '    function(inner)\n'
        '        cmake_parse_arguments(ARG "QUIET" "" "" ${ARGN})\n'
        '    endfunction()\n'
        'endfunction()\n'
    )
    assert outer.name == 'outer'
    assert outer.signature.accepts[ParamKind.Option] is None
    assert inner.signature.accepts[ParamKind.Option] == ['QUIET']


def test_named_positional_parameters_are_read(symbols_of):
    symbol = symbols_of('function(f NAME TYPE)\nendfunction()\n')[0]
    assert symbol.signature.accepts[ParamKind.Positional] == ['NAME', 'TYPE']


def test_a_definition_without_named_parameters_says_nothing(symbols_of):
    # It may still take arguments through ARGV0/ARGN, so an empty list would
    # be a claim the code does not make.
    symbol = symbols_of('function(f)\nendfunction()\n')[0]
    assert symbol.signature.accepts[ParamKind.Positional] is None


def test_macros_have_signatures_too(symbols_of):
    symbol = symbols_of(
        'macro(m NAME)\n    cmake_parse_arguments(ARG "" "T" "" ${ARGN})\nendmacro()\n'
    )[0]
    assert symbol.signature.accepts[ParamKind.Positional] == ['NAME']
    assert symbol.signature.accepts[ParamKind.SingleArgParam] == ['T']


def test_declares_reports_the_kind_a_name_is_taken_as(symbols_of):
    symbol = symbols_of(
        'function(f NAME)\n'
        '    cmake_parse_arguments(ARG "QUIET" "" "" ${ARGN})\n'
        'endfunction()\n'
    )[0]
    assert symbol.signature.declares('QUIET') == ParamKind.Option
    assert symbol.signature.declares('NAME') == ParamKind.Positional
    assert symbol.signature.declares('NOPE') is None
