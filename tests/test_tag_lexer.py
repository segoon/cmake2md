from cmake2md import tag_lexer
from cmake2md.tag_lexer import Tag


def test_plain_text():
    assert tag_lexer.tokenize(['hello world']) == ['hello world']


def test_empty():
    assert tag_lexer.tokenize([]) == []
    assert tag_lexer.tokenize(['']) == []


def test_tag_with_text():
    assert tag_lexer.tokenize([' @param FOO the foo']) == [
        ' ',
        Tag('param'),
        ' FOO the foo',
    ]


def test_tag_at_start_of_text():
    assert tag_lexer.tokenize(['@required']) == [Tag('required')]


def test_tag_names_may_contain_underscores_and_digits():
    assert tag_lexer.tokenize(['@param_x2 FOO']) == [Tag('param_x2'), ' FOO']


def test_email_is_not_a_tag():
    assert tag_lexer.tokenize(['mail to foo@example.com']) == [
        'mail to foo@example.com'
    ]


def test_bare_at_sign_is_literal():
    assert tag_lexer.tokenize(['costs 5 @ each']) == ['costs 5 @ each']


def test_double_at_is_an_escaped_literal():
    assert tag_lexer.tokenize(['a literal @@param sign']) == ['a literal @param sign']


def test_adjacent_tags():
    assert tag_lexer.tokenize(['@option FOO @required']) == [
        Tag('option'),
        ' FOO ',
        Tag('required'),
    ]


def test_lines_are_joined_with_newlines():
    assert tag_lexer.tokenize(['first', 'second']) == ['first\nsecond']


def test_tag_after_newline():
    assert tag_lexer.tokenize(['text', '@arg NAME']) == [
        'text\n',
        Tag('arg'),
        ' NAME',
    ]


def test_line_numbers_are_one_based_within_the_block():
    tokens = tag_lexer.tokenize(['first', 'second @arg NAME'])
    tags = [t for t in tokens if isinstance(t, Tag)]
    assert [t.line for t in tags] == [2]


def test_line_number_is_not_part_of_equality():
    assert Tag('arg', line=7) == Tag('arg', line=1)
