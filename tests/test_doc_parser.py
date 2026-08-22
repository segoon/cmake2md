import pytest

from cmake2md import doc_parser
from cmake2md import tag_lexer
from cmake2md.doc_parser import ParamKind
from cmake2md.errors import ParseError


def parse(*lines, strict=False):
    return doc_parser.parse(tag_lexer.tokenize(list(lines)), strict=strict)


def test_description_only():
    doc = parse(' Adds a library.', ' Really.')
    assert doc.description == 'Adds a library.\n Really.'
    assert doc.args == []
    assert doc.group is None


def test_positional_arg_is_required():
    doc = parse(' @arg NAME the target name')
    assert len(doc.args) == 1
    arg = doc.args[0]
    assert arg.kind == ParamKind.Positional
    assert arg.name == 'NAME'
    assert arg.description == 'the target name'
    assert arg.required


def test_option_is_optional_by_default():
    doc = parse(' @option QUIET be quiet')
    assert not doc.options[0].required


def test_required_applies_to_the_preceding_param():
    doc = parse(' @param OUTPUT_NAME @required the file name')
    assert doc.params[0].name == 'OUTPUT_NAME'
    assert doc.params[0].required
    assert doc.params[0].description == 'the file name'


def test_required_without_a_param_is_an_error():
    with pytest.raises(ParseError, match='@required must follow'):
        parse(' @required')


def test_params_are_split_by_kind_and_keep_order():
    doc = parse(
        ' Description.',
        ' @arg NAME n',
        ' @option QUIET q',
        ' @param TIMEOUT t',
        ' @multiparam SOURCES s',
        ' @multiparam DEPENDS d',
    )
    assert doc.description == 'Description.'
    assert [p.name for p in doc.args] == ['NAME']
    assert [p.name for p in doc.options] == ['QUIET']
    assert [p.name for p in doc.params] == ['TIMEOUT']
    assert [p.name for p in doc.multi_params] == ['SOURCES', 'DEPENDS']


def test_ingroup():
    doc = parse(' @ingroup compilation')
    assert doc.group == 'compilation'


def test_ingroup_with_surrounding_description():
    doc = parse(' Build with sanitizers.', ' @ingroup compilation')
    assert doc.group == 'compilation'
    assert doc.description == 'Build with sanitizers.'


def test_multiline_param_description():
    doc = parse(' @param TIMEOUT seconds before', ' the test is killed')
    assert doc.params[0].description == 'seconds before\n the test is killed'


def test_unknown_tag_is_kept_as_text_with_a_warning():
    doc = parse(' see @deprecated notes')
    assert doc.description == 'see @deprecated notes'
    assert len(doc.warnings) == 1
    assert 'unknown tag @deprecated' in doc.warnings[0]


def test_unknown_tag_is_fatal_in_strict_mode():
    with pytest.raises(ParseError, match='unknown tag @deprecated'):
        parse(' see @deprecated notes', strict=True)


def test_missing_name_after_tag_is_an_error():
    with pytest.raises(ParseError, match='@param requires a name'):
        parse(' @param')


def test_tag_directly_followed_by_another_tag_is_an_error():
    with pytest.raises(ParseError, match='@param requires a name'):
        parse(' @param @option QUIET q')


def test_email_in_description_survives():
    doc = parse(' Ask maintainer@example.com about it.')
    assert doc.description == 'Ask maintainer@example.com about it.'
    assert doc.warnings == []


def test_error_message_reports_the_line():
    with pytest.raises(ParseError, match='line 2'):
        parse(' first line', ' @required')
