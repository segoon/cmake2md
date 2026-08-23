import pytest

from cmake2doc.doc_parser import ParamKind


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
        ParamKind.OutVar: None,
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


def test_variables_set_in_the_parent_scope_are_read(accepts):
    assert accepts('set(RESULT "42" PARENT_SCOPE)\nset(COUNT 1 PARENT_SCOPE)')[
        ParamKind.OutVar
    ] == ['RESULT', 'COUNT']


def test_return_propagate_sets_variables_too(accepts):
    assert accepts('return(PROPAGATE OUT COUNT)')[ParamKind.OutVar] == ['OUT', 'COUNT']


def test_a_variable_set_in_two_branches_is_listed_once(accepts):
    assert accepts(
        'if(WIN32)\n'
        '    set(RESULT "w" PARENT_SCOPE)\n'
        'else()\n'
        '    set(RESULT "u" PARENT_SCOPE)\n'
        'endif()'
    )[ParamKind.OutVar] == ['RESULT']


def test_an_output_variable_named_by_the_caller_is_unknown(accepts):
    # The name is whatever the caller passed in, so the list cannot be read.
    assert accepts('set(${ARG_OUT} "v" PARENT_SCOPE)')[ParamKind.OutVar] is None


def test_a_definition_propagating_nothing_says_nothing(accepts):
    # Not "returns nothing": a macro sets its caller's variables directly, and
    # a function may write a cache entry or a global property instead.
    assert accepts('set(LOCAL "v")')[ParamKind.OutVar] is None


def test_a_nested_definitions_output_stays_its_own(symbols_of):
    outer, _ = symbols_of(
        'function(outer)\n'
        '    function(inner)\n'
        '        set(RESULT "x" PARENT_SCOPE)\n'
        '    endfunction()\n'
        'endfunction()\n'
    )
    assert outer.signature.accepts[ParamKind.OutVar] is None


def test_declares_reports_the_kind_a_name_is_taken_as(symbols_of):
    symbol = symbols_of(
        'function(f NAME)\n'
        '    cmake_parse_arguments(ARG "QUIET" "" "" ${ARGN})\n'
        'endfunction()\n'
    )[0]
    assert symbol.signature.declares('QUIET') == ParamKind.Option
    assert symbol.signature.declares('NAME') == ParamKind.Positional
    assert symbol.signature.declares('NOPE') is None
