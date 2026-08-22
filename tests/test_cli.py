import pathlib

import pytest

from cmake2md import cli

TEMPLATE = """\
{% for symbol in symbols %}
{{ symbol.pretty }}
{% endfor %}
| Option | Group |
|--------|-------|
{%- for cmd in commands | only_command('option') %}
| {{ cmd.args[0] }} | {{ cmd.group }} |
{%- endfor %}
"""


@pytest.fixture
def template(tmp_path):
    path = tmp_path / 'layout.md.jinja'
    path.write_text(TEMPLATE, encoding='utf-8')
    return path


def run(*argv):
    return cli.main([str(a) for a in argv])


def test_renders_functions_and_options(cmake_file, template, tmp_path):
    out = tmp_path / 'out.md'
    assert run('-t', template, '-o', out, cmake_file) == 0

    text = out.read_text(encoding='utf-8')
    assert '## example_add_library' in text
    assert 'Adds a library.' in text
    assert '<NAME>' in text
    assert '[EXCLUDE_FROM_ALL]' in text
    # @required promotes the param out of the square brackets.
    assert 'OUTPUT_NAME <value>' in text
    assert '[OUTPUT_NAME <value>]' not in text
    assert 'SOURCES <value>...' in text
    assert '| EXAMPLE_BUILD_TESTS | build |' in text
    assert '| EXAMPLE_STATIC | None |' in text


def test_output_ends_with_exactly_one_newline(cmake_file, template, tmp_path):
    out = tmp_path / 'out.md'
    run('-t', template, '-o', out, cmake_file)
    text = out.read_text(encoding='utf-8')
    assert text.endswith('\n')
    assert not text.endswith('\n\n')


def test_creates_missing_output_directories(cmake_file, template, tmp_path):
    out = tmp_path / 'deep' / 'nested' / 'out.md'
    assert run('-t', template, '-o', out, cmake_file) == 0
    assert out.exists()


def test_multiple_template_output_pairs(cmake_file, template, tmp_path):
    first = tmp_path / 'a.md'
    second = tmp_path / 'b.md'
    assert (
        run('-t', template, '-o', first, '-t', template, '-o', second, cmake_file) == 0
    )
    assert first.read_text(encoding='utf-8') == second.read_text(encoding='utf-8')


def test_macros_are_documented_too(cmake_file, template, tmp_path):
    out = tmp_path / 'out.md'
    assert run('-t', template, '-o', out, cmake_file) == 0
    assert '## example_warn' in out.read_text(encoding='utf-8')


def test_builtin_template_is_usable_by_name(cmake_file, tmp_path):
    out = tmp_path / 'out.md'
    assert run('-t', 'function.md.jinja', '-o', out, cmake_file) == 0

    text = out.read_text(encoding='utf-8')
    assert '## example_add_library' in text
    assert '## example_warn' in text
    # The built-in template filters undocumented symbols out.
    assert 'undocumented_function' not in text


def test_version_is_printed(capsys):
    from cmake2md import __version__

    with pytest.raises(SystemExit) as exc:
        run('--version')
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f'cmake2md {__version__}'


def test_unknown_template_says_where_it_looked(cmake_file, tmp_path, capsys):
    assert run('-t', 'nosuch.md.jinja', '-o', tmp_path / 'out.md', cmake_file) == 1
    err = capsys.readouterr().err
    assert 'template not found: nosuch.md.jinja' in err
    assert 'built-in templates: function.md.jinja' in err


def test_template_dir_is_searched(cmake_file, template, tmp_path):
    out = tmp_path / 'out.md'
    assert run('-I', template.parent, '-t', template.name, '-o', out, cmake_file) == 0


def test_check_reports_up_to_date(cmake_file, template, tmp_path):
    out = tmp_path / 'out.md'
    run('-t', template, '-o', out, cmake_file)
    assert run('--check', '-t', template, '-o', out, cmake_file) == 0


def test_check_reports_stale_output(cmake_file, template, tmp_path, capsys):
    out = tmp_path / 'out.md'
    out.write_text('stale\n', encoding='utf-8')
    assert run('--check', '-t', template, '-o', out, cmake_file) == 1
    assert out.read_text(encoding='utf-8') == 'stale\n'
    assert 'out of date' in capsys.readouterr().err


def test_check_reports_missing_output(cmake_file, template, tmp_path):
    out = tmp_path / 'out.md'
    assert run('--check', '-t', template, '-o', out, cmake_file) == 1
    assert not out.exists()


def test_unknown_tag_warns_but_succeeds(template, tmp_path, capsys):
    source = tmp_path / 'CMakeLists.txt'
    source.write_text('# @nosuchtag\nfunction(f)\nendfunction()\n', encoding='utf-8')
    out = tmp_path / 'out.md'
    assert run('-t', template, '-o', out, source) == 0
    err = capsys.readouterr().err
    assert 'unknown tag @nosuchtag' in err
    assert str(source) in err


def test_strict_rejects_unknown_tags(template, tmp_path, capsys):
    source = tmp_path / 'CMakeLists.txt'
    source.write_text('# @nosuchtag\nfunction(f)\nendfunction()\n', encoding='utf-8')
    out = tmp_path / 'out.md'
    assert run('--strict', '-t', template, '-o', out, source) == 1
    assert 'unknown tag @nosuchtag' in capsys.readouterr().err


def test_error_message_points_at_the_symbol(template, tmp_path, capsys):
    source = tmp_path / 'CMakeLists.txt'
    source.write_text('# @param\nfunction(broken)\nendfunction()\n', encoding='utf-8')
    out = tmp_path / 'out.md'
    assert run('-t', template, '-o', out, source) == 1
    err = capsys.readouterr().err
    assert 'broken' in err
    assert '@param requires a name' in err


def test_error_points_at_the_line_the_tag_is_on(template, tmp_path, capsys):
    source = tmp_path / 'CMakeLists.txt'
    # The comment block starts on line 3 and the bad tag is on line 5, two
    # lines above the function() the old message used to point at.
    source.write_text(
        'set(A 1)\n\n# Doc line one.\n# Doc line two.\n# Trouble: @param\n'
        'function(broken)\nendfunction()\n',
        encoding='utf-8',
    )
    assert run('-t', template, '-o', tmp_path / 'out.md', source) == 1
    err = capsys.readouterr().err
    assert f'{source}:5: function broken: @param requires a name' in err


def test_warning_points_at_the_line_the_tag_is_on(template, tmp_path, capsys):
    source = tmp_path / 'CMakeLists.txt'
    source.write_text(
        '# Doc line one.\n# Not tagged with @ingroup, so it is ungrouped.\n'
        'function(f)\nendfunction()\n',
        encoding='utf-8',
    )
    assert run('-t', template, '-o', tmp_path / 'out.md', source) == 0
    assert f'{source}:2: function f: warning:' in capsys.readouterr().err


MISMATCHED_SOURCE = """\
# Adds a thing.
#
# @option QUIET be quiet
# @multiparam SRCS the sources
function(add_thing)
    cmake_parse_arguments(ARG "QUIET" "" "SOURCES" ${ARGN})
endfunction()
"""


def test_documentation_disagreeing_with_the_code_warns(template, tmp_path, capsys):
    source = tmp_path / 'CMakeLists.txt'
    source.write_text(MISMATCHED_SOURCE, encoding='utf-8')
    assert run('-t', template, '-o', tmp_path / 'out.md', source) == 0

    err = capsys.readouterr().err
    assert f'{source}:4: function add_thing: warning: SRCS is documented' in err
    assert 'add_thing takes SOURCES but it is not documented' in err


def test_strict_rejects_documentation_disagreeing_with_the_code(
    template, tmp_path, capsys
):
    source = tmp_path / 'CMakeLists.txt'
    source.write_text(MISMATCHED_SOURCE, encoding='utf-8')
    assert run('--strict', '-t', template, '-o', tmp_path / 'out.md', source) == 1
    assert 'SRCS is documented as @multiparam' in capsys.readouterr().err


SECTIONED_SOURCE = """\
# @brief Adds a thing.
#
# The longer description.
#
# @note Call it early.
# @example
# add_thing(NAME x)
function(add_thing)
endfunction()

# A helper nobody outside should call.
#
# @internal
function(_helper)
endfunction()
"""


def test_builtin_template_renders_the_new_sections(tmp_path):
    source = tmp_path / 'CMakeLists.txt'
    source.write_text(SECTIONED_SOURCE, encoding='utf-8')
    out = tmp_path / 'out.md'
    assert run('-t', 'function.md.jinja', '-o', out, source) == 0

    text = out.read_text(encoding='utf-8')
    assert 'Adds a thing.' in text
    assert 'The longer description.' in text
    assert '> **Note:** Call it early.' in text
    assert '```cmake\nadd_thing(NAME x)\n```' in text
    # @internal keeps a documented helper out of the public reference.
    assert '_helper' not in text


GROUPED_SOURCE = """\
# @defgroup build Build targets
#
# What gets built.

# @defgroup paths Paths
#
# Where to look.

# @ingroup build
option(A "d" ON)
"""


def test_groups_carry_their_title_description_and_order(tmp_path):
    source = tmp_path / 'CMakeLists.txt'
    source.write_text(GROUPED_SOURCE, encoding='utf-8')
    group_template = tmp_path / 'groups.md.jinja'
    group_template.write_text(
        '{% for g in groups %}{{ g.name }}|{{ g.title }}|{{ g.description }}\n'
        '{% endfor %}',
        encoding='utf-8',
    )
    out = tmp_path / 'out.md'
    assert run('-t', group_template, '-o', out, source) == 0
    assert out.read_text(encoding='utf-8').splitlines() == [
        'build|Build targets|What gets built.',
        'paths|Paths|Where to look.',
    ]


def test_ingroup_naming_an_undefined_group_warns(template, tmp_path, capsys):
    source = tmp_path / 'CMakeLists.txt'
    source.write_text(
        GROUPED_SOURCE + '\n# @ingroup nosuch\noption(B "d" ON)\n', encoding='utf-8'
    )
    assert run('-t', template, '-o', tmp_path / 'out.md', source) == 0
    assert '@ingroup nosuch names a group that no @defgroup defines' in (
        capsys.readouterr().err
    )


def test_ingroup_is_not_checked_when_no_group_is_defined(template, tmp_path, capsys):
    source = tmp_path / 'CMakeLists.txt'
    source.write_text('# @ingroup build\noption(A "d" ON)\n', encoding='utf-8')
    assert run('-t', template, '-o', tmp_path / 'out.md', source) == 0
    assert 'names a group' not in capsys.readouterr().err


def test_defgroup_on_a_symbol_is_reported(template, tmp_path, capsys):
    source = tmp_path / 'CMakeLists.txt'
    source.write_text(
        '# @defgroup build Build targets\nfunction(f)\nendfunction()\n',
        encoding='utf-8',
    )
    assert run('-t', template, '-o', tmp_path / 'out.md', source) == 0
    assert 'defines nothing; a group is defined in a comment block' in (
        capsys.readouterr().err
    )


def test_variables_reach_templates_already_parsed(cmake_file, tmp_path):
    var_template = tmp_path / 'vars.md.jinja'
    var_template.write_text(
        '{% for v in variables %}{{ v.name }}={{ v.default }}'
        ' ({{ v.type_ }}, {{ v.docstring }}, {{ v.group }})\n{% endfor %}',
        encoding='utf-8',
    )
    out = tmp_path / 'out.md'
    assert run('-t', var_template, '-o', out, cmake_file) == 0
    assert out.read_text(encoding='utf-8').splitlines() == [
        'EXAMPLE_BUILD_TESTS=ON (BOOL, Build tests, build)',
        'EXAMPLE_STATIC=OFF (BOOL, Link statically, None)',
        'EXAMPLE_DIR=/opt/example (PATH, Where example lives, paths)',
    ]


def test_the_signature_is_available_to_templates(tmp_path):
    source = tmp_path / 'sig.cmake'
    source.write_text(
        '# Doc.\nfunction(f)\n'
        '    cmake_parse_arguments(ARG "QUIET" "" "" ${ARGN})\n'
        'endfunction()\n',
        encoding='utf-8',
    )
    sig_template = tmp_path / 'sig.md.jinja'
    sig_template.write_text(
        '{% for s in symbols %}{{ s.signature.accepts.option }}{% endfor %}',
        encoding='utf-8',
    )
    out = tmp_path / 'out.md'
    assert run('-t', sig_template, '-o', out, source) == 0
    assert out.read_text(encoding='utf-8').strip() == "['QUIET']"


def test_duplicate_symbol_is_reported(template, tmp_path, capsys):
    first = tmp_path / 'a.cmake'
    second = tmp_path / 'b.cmake'
    first.write_text('# Doc A\nfunction(dup)\nendfunction()\n', encoding='utf-8')
    second.write_text('# Doc B\nfunction(dup)\nendfunction()\n', encoding='utf-8')
    assert run('-t', template, '-o', tmp_path / 'out.md', first, second) == 0
    err = capsys.readouterr().err
    assert 'dup is already defined' in err
    assert str(first) in err


def test_two_templates_may_not_share_one_output(cmake_file, template, tmp_path):
    out = tmp_path / 'out.md'
    assert run('-t', template, '-o', out, '-t', template, '-o', out, cmake_file) == 1


def test_list_templates_needs_no_source(capsys):
    assert run('--list-templates') == 0
    assert 'function.md.jinja' in capsys.readouterr().out


def test_output_dash_writes_to_stdout(cmake_file, template, capsys):
    assert run('-t', template, '-o', '-', cmake_file) == 0
    assert '## example_add_library' in capsys.readouterr().out


def test_output_dash_is_rejected_with_check(cmake_file, template, capsys):
    assert run('--check', '-t', template, '-o', '-', cmake_file) == 1
    assert 'writes nothing to check' in capsys.readouterr().err


def test_directory_is_searched_for_cmake_sources(template, tmp_path):
    (tmp_path / 'sub').mkdir()
    (tmp_path / 'CMakeLists.txt').write_text(
        '# Doc\nfunction(top)\nendfunction()\n', encoding='utf-8'
    )
    (tmp_path / 'sub' / 'helpers.cmake').write_text(
        '# Doc\nfunction(nested)\nendfunction()\n', encoding='utf-8'
    )
    (tmp_path / 'sub' / 'notes.txt').write_text('function(ignored)\n', encoding='utf-8')

    out = tmp_path / 'out' / 'ref.md'
    assert run('-t', template, '-o', out, tmp_path) == 0
    text = out.read_text(encoding='utf-8')
    assert '## top' in text
    assert '## nested' in text
    assert 'ignored' not in text


def test_glob_pattern_is_expanded(template, tmp_path):
    (tmp_path / 'a.cmake').write_text(
        '# Doc\nfunction(from_glob)\nendfunction()\n', encoding='utf-8'
    )
    out = tmp_path / 'out.md'
    assert run('-t', template, '-o', out, tmp_path / '*.cmake') == 0
    assert '## from_glob' in out.read_text(encoding='utf-8')


def test_no_source_given_is_a_usage_error(template, tmp_path, capsys):
    assert run('-t', template, '-o', tmp_path / 'out.md') == 1
    assert 'no CMAKE_FILE given' in capsys.readouterr().err


def test_missing_template_is_a_usage_error(cmake_file, tmp_path, capsys):
    assert run('-o', tmp_path / 'out.md', cmake_file) == 1
    assert 'no --template given' in capsys.readouterr().err


def test_mismatched_template_and_output_counts(cmake_file, template, tmp_path, capsys):
    assert run('-t', template, '-t', template, '-o', tmp_path / 'a.md', cmake_file) == 1
    assert 'each template needs exactly one output' in capsys.readouterr().err


def test_legacy_colon_syntax_gets_a_helpful_message(cmake_file, template, capsys):
    assert run('-t', f'{template}:out.md', cmake_file) == 1
    assert 'no longer supported' in capsys.readouterr().err


def test_missing_source_is_reported(template, tmp_path, capsys):
    assert run('-t', template, '-o', tmp_path / 'out.md', tmp_path / 'gone.txt') == 1
    assert 'no CMake sources found' in capsys.readouterr().err


def test_non_utf8_source_is_reported_without_a_traceback(template, tmp_path, capsys):
    source = tmp_path / 'CMakeLists.txt'
    source.write_bytes('# caf\xe9\nfunction(f)\nendfunction()\n'.encode('latin-1'))
    assert run('-t', template, '-o', tmp_path / 'out.md', source) == 1
    assert 'not valid UTF-8' in capsys.readouterr().err


def test_example_renders(tmp_path):
    root = pathlib.Path(__file__).resolve().parent.parent
    out = tmp_path / 'reference.md'
    assert (
        run(
            '-t',
            root / 'examples' / 'reference.md.jinja',
            '-o',
            out,
            root / 'examples' / 'CMakeLists.txt',
        )
        == 0
    )
    text = out.read_text(encoding='utf-8')
    assert '## example_add_library' in text
    assert '## example_fail' in text
    assert 'maintainer@example.com' in text
    assert 'a literal @@' not in text
    assert '`EXAMPLE_BUILD_TESTS`' in text
    assert '`EXAMPLE_TOOLCHAIN_DIR`' in text
    # An @ingroup merely mentioned in prose must not group the option away
    # from the ungrouped table.
    assert '`EXAMPLE_STATIC`' in text
    assert '_example_internal_helper' not in text


FILE_DOC_SOURCE = """\
# @file
# @brief Helpers for building libraries.
#
# The longer story about this file.

function(f)
endfunction()
"""


def test_file_documentation_reaches_templates(tmp_path):
    source = tmp_path / 'helpers.cmake'
    source.write_text(FILE_DOC_SOURCE, encoding='utf-8')
    file_template = tmp_path / 'files.md.jinja'
    file_template.write_text(
        '{% for f in files %}{{ f.doc.brief }}|{{ f.doc.description }}\n{% endfor %}',
        encoding='utf-8',
    )
    out = tmp_path / 'out.md'
    assert run('-t', file_template, '-o', out, source) == 0
    assert out.read_text(encoding='utf-8').strip() == (
        'Helpers for building libraries.|The longer story about this file.'
    )


def test_see_links_to_a_symbol_the_document_defines(tmp_path):
    source = tmp_path / 'CMakeLists.txt'
    source.write_text(
        '# Adds a test.\n#\n# @see add_lib\n# @see other_project_fn\n'
        'function(add_test_target)\nendfunction()\n\n'
        '# Adds a library.\nfunction(add_lib)\nendfunction()\n',
        encoding='utf-8',
    )
    out = tmp_path / 'out.md'
    assert run('-t', 'function.md.jinja', '-o', out, source) == 0
    text = out.read_text(encoding='utf-8')
    assert '[add_lib](#add_lib)' in text
    # A name this document does not define is left as prose.
    assert 'other_project_fn' in text
    assert '[other_project_fn]' not in text


def test_parameter_type_and_default_are_rendered(tmp_path):
    source = tmp_path / 'CMakeLists.txt'
    source.write_text(
        '# Adds a test.\n#\n'
        '# @param TIMEOUT @type seconds @default 30 before it is killed\n'
        'function(f)\n'
        '    cmake_parse_arguments(ARG "" "TIMEOUT" "" ${ARGN})\n'
        'endfunction()\n',
        encoding='utf-8',
    )
    out = tmp_path / 'out.md'
    assert run('-t', 'function.md.jinja', '-o', out, source) == 0
    assert '(seconds, default `30`)' in out.read_text(encoding='utf-8')


def test_json_dump_carries_the_model_and_a_schema_version(cmake_file, tmp_path):
    import json

    out = tmp_path / 'model.json'
    assert (
        run(
            '-t',
            'function.md.jinja',
            '-o',
            tmp_path / 'o.md',
            '--json',
            out,
            cmake_file,
        )
        == 0
    )

    data = json.loads(out.read_text(encoding='utf-8'))
    assert data['schema_version'] >= 1
    names = [s['name'] for s in data['symbols']]
    assert 'example_add_library' in names

    symbol = next(s for s in data['symbols'] if s['name'] == 'example_add_library')
    # The parsed comment is plain data, not a repr of the dataclass.
    assert symbol['doc']['args'][0]['name'] == 'NAME'
    assert symbol['doc']['params'][0]['required'] is True
    assert [v['name'] for v in data['variables']] == [
        'EXAMPLE_BUILD_TESTS',
        'EXAMPLE_STATIC',
        'EXAMPLE_DIR',
    ]


def test_json_to_stdout_is_rejected_with_check(cmake_file, template, tmp_path, capsys):
    assert (
        run(
            '--check',
            '-t',
            template,
            '-o',
            tmp_path / 'o.md',
            '--json',
            '-',
            cmake_file,
        )
        == 1
    )
    assert 'writes nothing to check' in capsys.readouterr().err


UNDOCUMENTED_SOURCE = """\
# Documented.
function(documented)
endfunction()

function(bare)
endfunction()

function(_private)
endfunction()

# Documented but private.
#
# @internal
function(helper)
endfunction()
"""


def test_require_docs_reports_only_public_undocumented_symbols(
    template, tmp_path, capsys
):
    source = tmp_path / 'CMakeLists.txt'
    source.write_text(UNDOCUMENTED_SOURCE, encoding='utf-8')
    assert run('--require-docs', '-t', template, '-o', tmp_path / 'o.md', source) == 1

    err = capsys.readouterr().err
    assert 'function bare: error: undocumented' in err
    # A leading underscore and an explicit @internal both mean private.
    assert '_private' not in err
    assert 'helper' not in err


def test_without_require_docs_an_undocumented_symbol_is_fine(
    template, tmp_path, capsys
):
    source = tmp_path / 'CMakeLists.txt'
    source.write_text(UNDOCUMENTED_SOURCE, encoding='utf-8')
    assert run('-t', template, '-o', tmp_path / 'o.md', source) == 0
    assert 'undocumented' not in capsys.readouterr().err


def test_check_shows_what_differs(cmake_file, template, tmp_path, capsys):
    out = tmp_path / 'out.md'
    out.write_text('stale\n', encoding='utf-8')
    assert run('--check', '-t', template, '-o', out, cmake_file) == 1

    err = capsys.readouterr().err
    assert 'out of date' in err
    assert '-stale' in err
    assert '(generated)' in err


def test_exclude_skips_matching_sources(template, tmp_path):
    (tmp_path / 'tests').mkdir()
    (tmp_path / 'a.cmake').write_text(
        '# Doc\nfunction(kept)\nendfunction()\n', encoding='utf-8'
    )
    (tmp_path / 'tests' / 'b.cmake').write_text(
        '# Doc\nfunction(skipped)\nendfunction()\n', encoding='utf-8'
    )
    out = tmp_path / 'out.md'
    assert run('--exclude', '*/tests/*', '-t', template, '-o', out, tmp_path) == 0

    text = out.read_text(encoding='utf-8')
    assert '## kept' in text
    assert 'skipped' not in text


def test_exclude_matches_a_bare_file_name_too(template, tmp_path):
    (tmp_path / 'a.cmake').write_text(
        '# Doc\nfunction(kept)\nendfunction()\n', encoding='utf-8'
    )
    (tmp_path / 'test_helpers.cmake').write_text(
        '# Doc\nfunction(skipped)\nendfunction()\n', encoding='utf-8'
    )
    out = tmp_path / 'out.md'
    assert run('--exclude', 'test_*.cmake', '-t', template, '-o', out, tmp_path) == 0
    assert 'skipped' not in out.read_text(encoding='utf-8')


def test_ignore_file_adds_exclusions(template, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / '.cmake2mdignore').write_text(
        '# what CI does not document\ntest_*.cmake\n', encoding='utf-8'
    )
    (tmp_path / 'a.cmake').write_text(
        '# Doc\nfunction(kept)\nendfunction()\n', encoding='utf-8'
    )
    (tmp_path / 'test_helpers.cmake').write_text(
        '# Doc\nfunction(skipped)\nendfunction()\n', encoding='utf-8'
    )
    out = tmp_path / 'out.md'
    assert run('-t', template, '-o', out, tmp_path) == 0

    text = out.read_text(encoding='utf-8')
    assert '## kept' in text
    assert 'skipped' not in text


INJECTABLE = """\
# My project

Prose the author wrote.

<!-- BEGIN_CMAKE2MD -->
what was generated last time
<!-- END_CMAKE2MD -->

Prose after it.
"""


def test_inject_replaces_only_what_is_between_the_markers(
    cmake_file, template, tmp_path
):
    out = tmp_path / 'README.md'
    out.write_text(INJECTABLE, encoding='utf-8')
    assert run('--inject', '-t', template, '-o', out, cmake_file) == 0

    text = out.read_text(encoding='utf-8')
    assert text.startswith('# My project\n\nProse the author wrote.\n')
    assert text.endswith('Prose after it.\n')
    assert '## example_add_library' in text
    assert 'what was generated last time' not in text


def test_inject_is_idempotent(cmake_file, template, tmp_path):
    out = tmp_path / 'README.md'
    out.write_text(INJECTABLE, encoding='utf-8')
    run('--inject', '-t', template, '-o', out, cmake_file)
    once = out.read_text(encoding='utf-8')
    run('--inject', '-t', template, '-o', out, cmake_file)
    assert out.read_text(encoding='utf-8') == once
    # And --check agrees that there is nothing to do.
    assert run('--check', '--inject', '-t', template, '-o', out, cmake_file) == 0


def test_inject_without_markers_says_what_is_missing(
    cmake_file, template, tmp_path, capsys
):
    out = tmp_path / 'README.md'
    out.write_text('# My project\n', encoding='utf-8')
    assert run('--inject', '-t', template, '-o', out, cmake_file) == 1
    assert 'no place to inject into' in capsys.readouterr().err


def test_inject_needs_the_file_to_exist(cmake_file, template, tmp_path, capsys):
    assert run('--inject', '-t', template, '-o', tmp_path / 'nope.md', cmake_file) == 1
    assert '--inject needs' in capsys.readouterr().err


def test_builtin_reference_template_documents_a_whole_project(cmake_file, tmp_path):
    out = tmp_path / 'ref.md'
    assert run('-t', 'reference.md.jinja', '-o', out, cmake_file) == 0

    text = out.read_text(encoding='utf-8')
    assert '## Contents' in text
    assert '[example_add_library](#example_add_library)' in text
    assert '## Build options' in text
    assert '| `EXAMPLE_BUILD_TESTS` |' in text
    # Undocumented symbols stay out, as in the other built-in template.
    assert 'undocumented_function' not in text


def test_reference_template_lays_itself_out_by_group(tmp_path):
    source = tmp_path / 'CMakeLists.txt'
    source.write_text(
        '# @defgroup targets Targets\n'
        '#\n'
        '# Adding things to build.\n'
        '\n'
        '# Adds a library.\n'
        '#\n'
        '# @ingroup targets\n'
        'function(add_lib)\n'
        'endfunction()\n'
        '\n'
        '# In no group at all.\n'
        'function(loose_one)\n'
        'endfunction()\n',
        encoding='utf-8',
    )
    out = tmp_path / 'ref.md'
    assert run('-t', 'reference.md.jinja', '-o', out, source) == 0

    text = out.read_text(encoding='utf-8')
    assert '## Targets' in text
    assert 'Adding things to build.' in text
    # What no group claims still gets a home.
    assert '## Functions and macros' in text
    assert '## loose_one' in text


def test_list_templates_names_both_builtins(capsys):
    assert run('--list-templates') == 0
    out = capsys.readouterr().out
    assert 'function.md.jinja' in out
    assert 'reference.md.jinja' in out
