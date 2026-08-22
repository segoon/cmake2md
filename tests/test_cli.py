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
