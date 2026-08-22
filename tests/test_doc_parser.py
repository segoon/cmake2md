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


def test_return_documents_an_output_variable():
    doc = parse(' @set_parent_scope RESULT the computed value')
    assert doc.returns[0].kind == ParamKind.OutVar
    assert doc.returns[0].name == 'RESULT'
    assert doc.returns[0].description == 'the computed value'


def test_brief_is_the_summary_and_ends_at_a_blank_line():
    doc = parse(
        ' @brief Adds a library.',
        '',
        ' The longer story, which is not part of the brief.',
    )
    assert doc.brief == 'Adds a library.'
    assert doc.description == 'The longer story, which is not part of the brief.'


def test_brief_keeps_prose_written_before_it():
    doc = parse(' Leading prose.', ' @brief The summary.')
    assert doc.brief == 'The summary.'
    assert doc.description == 'Leading prose.'


def test_prose_sections_are_collected_in_order():
    doc = parse(
        ' Adds a library.',
        ' @note Call it early.',
        ' @warning Not thread safe.',
        ' @since 1.2',
        ' @todo support OBJECT libraries',
        ' @see example_add_test',
    )
    assert [(s.kind, s.text) for s in doc.sections] == [
        ('note', 'Call it early.'),
        ('warning', 'Not thread safe.'),
        ('since', '1.2'),
        ('todo', 'support OBJECT libraries'),
        ('see', 'example_add_test'),
    ]
    assert doc.description == 'Adds a library.'


def test_of_kind_selects_sections():
    doc = parse(' @note One.', ' @warning Careful.', ' @note Two.')
    assert [s.text for s in doc.of_kind('note')] == ['One.', 'Two.']
    assert doc.of_kind('nosuch') == []


def test_a_prose_section_ends_at_a_blank_line():
    doc = parse(' @note Call it early.', '', ' Back to the description.')
    assert doc.of_kind('note')[0].text == 'Call it early.'
    assert doc.description == 'Back to the description.'


def test_an_example_keeps_its_blank_lines():
    doc = parse(
        ' @example',
        ' f(A)',
        '',
        ' g(B)',
        ' @note And a note.',
    )
    assert doc.of_kind('example')[0].text == 'f(A)\n\n g(B)'
    assert doc.of_kind('note')[0].text == 'And a note.'


def test_a_section_does_not_swallow_the_parameters_that_follow():
    doc = parse(' @note Careful.', ' @param NAME the name')
    assert doc.of_kind('note')[0].text == 'Careful.'
    assert [(p.name, p.description) for p in doc.params] == [('NAME', 'the name')]


def test_internal_is_a_symbol_level_flag():
    assert not parse(' A helper.').internal
    doc = parse(' A helper.', ' @internal')
    assert doc.internal
    assert doc.description == 'A helper.'


def test_sections_carry_the_line_they_are_on():
    doc = doc_parser.parse(
        tag_lexer.tokenize([' first line', ' @note here']), first_line=40
    )
    assert doc.of_kind('note')[0].line == 41


def test_defgroup_takes_a_name_and_a_title():
    doc = parse(
        ' @defgroup build Build targets',
        '',
        ' What gets built, and what is left out.',
    )
    section = doc.of_kind('defgroup')[0]
    assert section.name == 'build'
    assert section.text == 'Build targets'
    assert doc.description == 'What gets built, and what is left out.'


def test_defgroup_without_a_title_keeps_an_empty_one():
    assert doc_parser.parse(tag_lexer.tokenize([' @defgroup build'])).of_kind(
        'defgroup'
    )[0] == doc_parser.Section(kind='defgroup', text='', name='build', line=1)


def test_ingroup():
    doc = parse(' @ingroup compilation')
    assert doc.group == 'compilation'
    assert doc.group_line == 1


def test_ingroup_with_surrounding_description():
    doc = parse(' Build with sanitizers.', ' @ingroup compilation')
    assert doc.group == 'compilation'
    assert doc.description == 'Build with sanitizers.'


def test_multiline_param_description():
    doc = parse(' @param TIMEOUT seconds before', ' the test is killed')
    assert doc.params[0].description == 'seconds before\n the test is killed'


def test_unknown_tag_is_kept_as_text_with_a_warning():
    doc = parse(' see @nosuchtag notes')
    assert doc.description == 'see @nosuchtag notes'
    assert len(doc.warnings) == 1
    assert 'unknown tag @nosuchtag' in doc.warnings[0].message


def test_unknown_tag_is_fatal_in_strict_mode():
    with pytest.raises(ParseError, match='unknown tag @nosuchtag'):
        parse(' see @nosuchtag notes', strict=True)


def test_deprecated_is_a_symbol_level_flag():
    assert not parse(' Adds a library.').deprecated

    # The prose after the tag stays in the description, where it reads as the
    # reason; only the tag itself is taken out.
    doc = parse(' Adds a library.', ' @deprecated use example_add_library2.')
    assert doc.deprecated
    # One space, the indentation of the comment line itself: the tag and the
    # space separating it from the text are both consumed.
    assert doc.description == 'Adds a library.\n use example_add_library2.'


def test_missing_name_after_tag_is_an_error():
    with pytest.raises(ParseError, match='@param requires a name'):
        parse(' @param')


def test_tag_directly_followed_by_another_tag_is_an_error():
    with pytest.raises(ParseError, match='@param requires a name'):
        parse(' @param @option QUIET q')


def test_tag_mentioned_in_prose_is_kept_as_text_with_a_warning():
    doc = parse(' Not tagged with @ingroup, so it is ungrouped.')
    assert doc.group is None
    assert doc.description == 'Not tagged with @ingroup, so it is ungrouped.'
    assert '@ingroup' in doc.warnings[0].message


def test_tag_mentioned_in_prose_is_fatal_in_strict_mode():
    with pytest.raises(ParseError, match='@ingroup'):
        parse(' Not tagged with @ingroup, so it is ungrouped.', strict=True)


def test_escaped_tag_in_prose_warns_about_nothing():
    doc = parse(' Not tagged with @@ingroup, so it is ungrouped.')
    assert doc.group is None
    assert doc.description == 'Not tagged with @ingroup, so it is ungrouped.'
    assert doc.warnings == []


def test_email_in_description_survives():
    doc = parse(' Ask maintainer@example.com about it.')
    assert doc.description == 'Ask maintainer@example.com about it.'
    assert doc.warnings == []


def test_error_reports_the_line_the_tag_is_on():
    with pytest.raises(ParseError) as exc:
        parse(' first line', ' @required')
    assert exc.value.line == 2


def test_lines_are_counted_from_where_the_comment_starts():
    # first_line is the file line of the comment's first line, so the tag on
    # its second line is on file line 41, not on line 2.
    with pytest.raises(ParseError) as exc:
        doc_parser.parse(
            tag_lexer.tokenize([' first line', ' @required']), first_line=40
        )
    assert exc.value.line == 41


def test_warnings_carry_the_line_too():
    doc = doc_parser.parse(
        tag_lexer.tokenize([' first line', ' see @nosuchtag']), first_line=40
    )
    assert [w.line for w in doc.warnings] == [41]


def test_type_and_default_refine_the_preceding_parameter():
    doc = parse(' @param TIMEOUT @type seconds @default 30 before it is killed')
    param = doc.params[0]
    assert param.type_ == 'seconds'
    assert param.default == '30'
    assert param.description == 'before it is killed'


def test_type_without_a_parameter_is_an_error():
    with pytest.raises(ParseError, match='@type must follow'):
        parse(' @type seconds')


def test_default_without_a_parameter_is_an_error():
    with pytest.raises(ParseError, match='@default must follow'):
        parse(' @default 30')


def test_file_marks_the_block_as_documenting_the_file():
    assert not parse(' Just prose.').documents_file
    doc = parse(' @file', ' @brief What this file is for.')
    assert doc.documents_file
    assert doc.brief == 'What this file is for.'
