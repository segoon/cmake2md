import pytest

from cmake2md import rendering
from cmake2md.errors import UsageError


def test_unquote():
    assert rendering.unquote('"hello"') == 'hello'
    assert rendering.unquote('hello') == 'hello'


def test_escape_quotes_variable_references():
    assert rendering.escape('${CMAKE_SOURCE_DIR}') == '"${CMAKE_SOURCE_DIR}"'
    assert rendering.escape('ON') == 'ON'


def test_md_escape_protects_table_cells():
    assert rendering.md_escape('a | b') == r'a \| b'
    assert rendering.md_escape('a\\b') == 'a\\\\b'
    assert rendering.md_escape('a\nb') == 'a b'


def test_oneline_joins_continuations():
    assert rendering.oneline('foo \\\nbar') == 'foo  bar'


def test_only_command_and_only_group():
    items: list[rendering.Item] = [
        {'name': 'option', 'group': 'build'},
        {'name': 'option', 'group': None},
        {'name': 'set', 'group': 'build'},
    ]
    assert rendering.only_command(items, 'option') == items[:2]
    assert rendering.only_group(items, 'build') == [items[0], items[2]]
    assert rendering.only_group(items, None) == [items[1]]


def test_only_group_tolerates_items_without_a_group():
    assert rendering.only_group([{'name': 'x'}], None) == [{'name': 'x'}]


def test_documented_keeps_only_commented_items():
    items: list[rendering.Item] = [
        {'name': 'a', 'comments': [' doc']},
        {'name': 'b', 'comments': []},
        {'name': 'c', 'comments': ['', '  ']},
    ]
    assert rendering.documented(items) == [items[0]]


def test_collapse_blank_lines():
    assert rendering.collapse_blank_lines('a\n\n\n\n\nb') == 'a\n\n\nb'
    assert rendering.collapse_blank_lines('a\n\nb') == 'a\n\nb'


def test_collapse_blank_lines_leaves_code_fences_alone():
    text = 'a\n\n\n\n```\nx\n\n\n\n\ny\n```\n\n\n\n\nb'
    result = rendering.collapse_blank_lines(text)
    assert '```\nx\n\n\n\n\ny\n```' in result
    assert result.startswith('a\n\n\n```')
    assert result.endswith('```\n\n\nb')


def test_resolve_template_spec_for_a_path(tmp_path):
    template = tmp_path / 'layout.md.jinja'
    template.write_text('x')
    assert rendering.resolve_template_spec(str(template)) == (
        tmp_path,
        'layout.md.jinja',
    )


def test_resolve_template_spec_for_a_name(tmp_path, monkeypatch):
    # A name that is not an existing file is looked up in the search path
    # instead, so this must not depend on the working directory.
    monkeypatch.chdir(tmp_path)
    assert rendering.resolve_template_spec('function.md.jinja') == (
        None,
        'function.md.jinja',
    )


def test_builtin_template_is_packaged():
    env = rendering.build_environment([])
    assert env.get_template(rendering.FUNCTION_TEMPLATE_NAME) is not None


def test_search_dirs_shadow_the_builtin_template(tmp_path):
    (tmp_path / rendering.FUNCTION_TEMPLATE_NAME).write_text('overridden')
    env = rendering.build_environment([tmp_path])
    template = env.get_template(rendering.FUNCTION_TEMPLATE_NAME)
    assert template.render({}) == 'overridden'


def test_load_template_reports_where_it_looked(tmp_path):
    env = rendering.build_environment([tmp_path])
    with pytest.raises(UsageError) as exc:
        rendering.load_template(env, 'nosuch.md.jinja', [tmp_path])
    message = str(exc.value)
    assert 'template not found: nosuch.md.jinja' in message
    assert str(tmp_path) in message
    assert rendering.FUNCTION_TEMPLATE_NAME in message
