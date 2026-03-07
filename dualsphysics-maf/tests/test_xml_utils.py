import pytest

from mcp_server.tools._xml_utils import preprocess_xml

pytestmark = pytest.mark.unit


def test_preprocess_xml_normalizes_comments_and_percent_comments():
    content = """<root>
<!--- comment-with---extra-dashes --->
<item value="1"></item> % inline comment
% line comment
</root>
"""

    fixed = preprocess_xml(content)

    assert "<!-- comment-with-extra-dashes -->" in fixed
    assert "% inline comment" not in fixed
    assert "% line comment" not in fixed


def test_preprocess_xml_escapes_angle_brackets_inside_attributes():
    content = '<root><item expr="x < 1 && y > 0" label="20% slope"></item></root>'

    fixed = preprocess_xml(content)

    assert 'expr="x &lt; 1 && y &gt; 0"' in fixed
    assert 'label="20% slope"' in fixed
