def test_option_is_read_with_its_default_and_help_string(variables_of):
    variable = variables_of('option(BUILD_TESTS "Build the tests" ON)\n')[0]
    assert variable.name == 'BUILD_TESTS'
    assert variable.command == 'option'
    assert variable.type_ == 'BOOL'
    assert variable.default == 'ON'
    assert variable.docstring == 'Build the tests'
    assert variable.choices is None


def test_an_option_without_a_default_is_off(variables_of):
    # What CMake itself does with it.
    assert variables_of('option(BUILD_TESTS "Build the tests")\n')[0].default == 'OFF'


def test_cache_set_is_read(variables_of):
    variable = variables_of('set(DIR "/opt/x" CACHE PATH "Where x lives")\n')[0]
    assert variable.name == 'DIR'
    assert variable.command == 'set'
    assert variable.type_ == 'PATH'
    assert variable.default == '/opt/x'
    assert variable.docstring == 'Where x lives'


def test_several_values_join_into_a_list_default(variables_of):
    # set(X a b CACHE STRING "d") makes X the list "a;b".
    assert variables_of('set(X a b CACHE STRING "d")\n')[0].default == 'a;b'


def test_a_set_without_cache_is_not_a_user_settable_variable(variables_of):
    assert variables_of('set(LOCAL_ONLY "x")\n') == []


def test_a_computed_name_is_skipped(variables_of):
    assert variables_of('option(${_prefix}_TESTS "d" ON)\n') == []


def test_other_commands_are_not_variables(variables_of):
    assert variables_of('project(x)\nadd_library(y)\n') == []


def test_choices_come_from_the_strings_property(variables_of):
    variable = variables_of(
        'set(SANITIZER "address" CACHE STRING "Which sanitizer")\n'
        'set_property(CACHE SANITIZER PROPERTY STRINGS address thread undefined)\n'
    )[0]
    assert variable.choices == ['address', 'thread', 'undefined']


def test_choices_given_as_one_list_are_split(variables_of):
    variable = variables_of(
        'set(S "a" CACHE STRING "d")\nset_property(CACHE S PROPERTY STRINGS "a;b;c")\n'
    )[0]
    assert variable.choices == ['a', 'b', 'c']


def test_one_set_property_may_constrain_several_entries(variables_of):
    variables = variables_of(
        'set(A "x" CACHE STRING "d")\n'
        'set(B "x" CACHE STRING "d")\n'
        'set_property(CACHE A B PROPERTY STRINGS x y)\n'
    )
    assert [v.choices for v in variables] == [['x', 'y'], ['x', 'y']]


def test_another_property_does_not_become_choices(variables_of):
    variable = variables_of(
        'set(S "a" CACHE STRING "d")\nset_property(CACHE S PROPERTY ADVANCED TRUE)\n'
    )[0]
    assert variable.choices is None


def test_the_doc_comment_is_attached(variables_of):
    variable = variables_of('# @ingroup build\noption(BUILD_TESTS "d" ON)\n')[0]
    assert [c.strip() for c in variable.comments] == ['@ingroup build']
    assert variable.comments_line == 1
    assert variable.line == 2


def test_variables_are_located_for_diagnostics(variables_of):
    option, cached = variables_of('option(A "d" ON)\nset(B "v" CACHE STRING "d")\n')
    assert option.location.endswith(':1: option A')
    assert cached.location.endswith(':2: cache variable B')


def test_mark_as_advanced_flags_the_entry(variables_of):
    plain, advanced = variables_of(
        'option(PLAIN "d" ON)\noption(DEEP "d" ON)\nmark_as_advanced(DEEP)\n'
    )
    assert not plain.advanced
    assert advanced.advanced


def test_mark_as_advanced_keywords_are_not_names(variables_of):
    variable = variables_of('option(DEEP "d" ON)\nmark_as_advanced(FORCE DEEP)\n')[0]
    assert variable.advanced
