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


def test_builtin_template_is_usable_by_name(cmake_file, tmp_path):
    out = tmp_path / 'out.md'
    assert run('-t', 'function.md.jinja', '-o', out, cmake_file) == 0


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


def test_missing_template_is_a_usage_error(cmake_file, tmp_path, capsys):
    assert run('-o', tmp_path / 'out.md', cmake_file) == 1
    assert 'no --template given' in capsys.readouterr().err


def test_mismatched_template_and_output_counts(cmake_file, template, tmp_path, capsys):
    assert run('-t', template, '-t', template, '-o', tmp_path / 'a.md', cmake_file) == 1
    assert 'each template needs exactly one output' in capsys.readouterr().err


def test_legacy_colon_syntax_gets_a_helpful_message(cmake_file, template, capsys):
    assert run('-t', f'{template}:out.md', cmake_file) == 1
    assert 'no longer supported' in capsys.readouterr().err


def test_unreadable_source_is_reported(template, tmp_path, capsys):
    assert run('-t', template, '-o', tmp_path / 'out.md', tmp_path / 'gone.txt') == 1
    assert 'cannot read' in capsys.readouterr().err


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
    assert 'maintainer@example.com' in text
    assert 'a literal @@' not in text
    assert '`EXAMPLE_BUILD_TESTS`' in text
    assert '`EXAMPLE_TOOLCHAIN_DIR`' in text
