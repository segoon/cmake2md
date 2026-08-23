def test_add_library_is_read(targets_of):
    target = targets_of('add_library(core STATIC a.cpp)\n')[0]
    assert target.name == 'core'
    assert target.command == 'add_library'
    assert target.kind == 'library'
    assert target.args == ['core', 'STATIC', 'a.cpp']


def test_add_executable_is_read(targets_of):
    target = targets_of('add_executable(app main.cpp)\n')[0]
    assert target.name == 'app'
    assert target.command == 'add_executable'
    assert target.kind == 'executable'


def test_add_custom_target_is_read(targets_of):
    target = targets_of('add_custom_target(docs)\n')[0]
    assert target.name == 'docs'
    assert target.command == 'add_custom_target'
    assert target.kind == 'custom target'


def test_add_test_legacy_form_names_the_first_argument(targets_of):
    target = targets_of('add_test(unit_tests unit_runner)\n')[0]
    assert target.name == 'unit_tests'
    assert target.command == 'add_test'
    assert target.kind == 'test'


def test_add_test_name_form_names_the_value_after_name(targets_of):
    target = targets_of('add_test(NAME unit_tests COMMAND unit_runner)\n')[0]
    assert target.name == 'unit_tests'
    assert target.kind == 'test'


def test_add_test_name_form_with_nothing_after_name_is_skipped(targets_of):
    assert targets_of('add_test(NAME)\n') == []


def test_a_computed_name_is_skipped(targets_of):
    assert targets_of('add_library(${_prefix}_core a.cpp)\n') == []


def test_add_custom_command_is_not_a_target(targets_of):
    # It names an OUTPUT or an existing TARGET, never a target of its own.
    assert targets_of('add_custom_command(OUTPUT out.h COMMAND gen)\n') == []


def test_other_commands_are_not_targets(targets_of):
    assert targets_of('project(x)\noption(BUILD_TESTS "d" ON)\n') == []


def test_the_doc_comment_is_attached(targets_of):
    target = targets_of('# @brief The core library.\nadd_library(core a.cpp)\n')[0]
    assert [c.strip() for c in target.comments] == ['@brief The core library.']
    assert target.comments_line == 1
    assert target.line == 2


def test_targets_are_located_for_diagnostics(targets_of):
    library, test = targets_of(
        'add_library(core a.cpp)\nadd_test(unit_tests unit_runner)\n'
    )
    assert library.location.endswith(':1: library core')
    assert test.location.endswith(':2: test unit_tests')
