import unittest
from xml.etree import ElementTree
from docmaptools import convert
from tests.helpers import read_fixture


class TestConvertHtml(unittest.TestCase):
    def test_html_to_xml(self):
        string = read_fixture("sample_page.html", mode="rb")
        expected = read_fixture("sample_page.xml", mode="rb")
        content = convert.convert_html_string(string)
        self.assertEqual(content, expected, "got %s" % content)

    def test_html_to_xml_parse_error(self):
        string = b"<p><strong><em>Test</strong></em><br></p>"
        expected = (
            b"<root><body><p><italic><bold>Test</bold></italic><br /></p></body></root>"
        )
        content = convert.convert_html_string(string)
        self.assertEqual(content, expected)

    def test_html_to_xml_edge_case(self):
        string = (
            b"<p>"
            b"<em><strong>Test</strong></em>"
            b"<ul><li><em>dot</em></li></ul>"
            b"</p>"
        )
        expected = (
            b"<root>"
            b"<body>"
            b"<p>"
            b"<italic><bold>Test</bold></italic>"
            b'<list list-type="bullet"><list-item><italic>dot</italic></list-item></list>'
            b"</p></body>"
            b"</root>"
        )
        content = convert.convert_html_string(string)
        self.assertEqual(content, expected)


def invoke_module_function(string, function_name):
    "parse into XML, invoke the convert module function, return XML string of the modified tree"
    root = ElementTree.fromstring(string)
    function = getattr(convert, function_name)
    if function:
        function(root)
    return ElementTree.tostring(root)


class TestBlockquoteTags(unittest.TestCase):
    def test_blockquote_tags(self):
        xml_string = (
            b"<root>"
            b"<blockquote>"
            b"Head. <p>First paragraph.</p> Tail."
            b"</blockquote>"
            b"<blockquote>"
            b"<p>Second paragraph.</p>"
            b"</blockquote>"
            b"<p>Paragraph.</p>"
            b"</root>"
        )
        expected = (
            b"<root>"
            b'<disp-quote content-type="editor-comment">'
            b"Head. <p>First paragraph.</p> Tail."
            b"<p>Second paragraph.</p>"
            b"</disp-quote>"
            b"<p>Paragraph.</p>"
            b"</root>"
        )
        xml_string = invoke_module_function(xml_string, "blockquote_tags")
        self.assertEqual(xml_string, expected)


class TestArticleTitleTag(unittest.TestCase):
    def test_article_title_tag(self):
        xml_string = (
            b"<root>"
            b"<p><bold>"
            b"An article title"
            b"</bold></p>"
            b"<p>Paragraph.</p>"
            b"</root>"
        )
        expected = (
            b"<root>"
            b"<title-group><article-title>"
            b"An article title"
            b"</article-title></title-group>"
            b"<p>Paragraph.</p>"
            b"</root>"
        )
        self.assertEqual(
            invoke_module_function(xml_string, "article_title_tag"), expected
        )

    def test_article_title_tag_italic(self):
        "test italic tag inside the title"
        article_title_xml = b"<italic>An article title</italic>"
        xml_string = (
            b"<root>" b"<p><bold>" b"%s" b"</bold></p>" b"</root>"
        ) % article_title_xml
        expected = (
            b"<root>"
            b"<title-group><article-title>"
            b"%s"
            b"</article-title></title-group>"
            b"</root>"
        ) % article_title_xml
        self.assertEqual(
            invoke_module_function(xml_string, "article_title_tag"), expected
        )

    def test_article_title_tag_not_bold(self):
        "test if bold tag is not the first tag"
        xml_string = (
            b"<root>"
            b"<p>"
            b"<italic><bold>An article title</bold></italic>"
            b"</p>"
            b"</root>"
        )
        expected = xml_string
        self.assertEqual(
            invoke_module_function(xml_string, "article_title_tag"), expected
        )


class TestFrontStubTag(unittest.TestCase):
    def test_front_stub_tagp(self):
        title_group_xml = (
            b"<title-group><article-title>Title</article-title></title-group>"
        )
        xml_string = b"<root>%s</root>" % title_group_xml
        expected = b"<root><front-stub>%s</front-stub></root>" % title_group_xml
        self.assertEqual(invoke_module_function(xml_string, "front_stub_tag"), expected)

    def test_front_stub_tag_no_title_group(self):
        xml_string = b"<root><p>Paragraph.</p></root>"
        expected = xml_string
        self.assertEqual(invoke_module_function(xml_string, "front_stub_tag"), expected)


class TestBodyTag(unittest.TestCase):
    def test_body_tag(self):
        front_stub_xml = (
            b"<front-stub>"
            b"<title-group>"
            b"<article-title>Title</article-title>"
            b"</title-group>"
            b"</front-stub>"
        )
        body_xml = b"<p>Paragraph.</p>"
        xml_string = b"<root>%s%s</root>" % (front_stub_xml, body_xml)
        expected = b"<root>%s<body>%s</body></root>" % (front_stub_xml, body_xml)
        self.assertEqual(invoke_module_function(xml_string, "body_tag"), expected)

    def test_body_tag_no_front_stub(self):
        body_xml = b"<p>Paragraph.</p>"
        xml_string = b"<root>%s</root>" % body_xml
        expected = b"<root><body>%s</body></root>" % body_xml
        self.assertEqual(invoke_module_function(xml_string, "body_tag"), expected)


class TestReplaceTags(unittest.TestCase):
    def test_replace_tags_em(self):
        xml_string = b"<root><em/></root>"
        expected = b"<root><italic /></root>"
        self.assertEqual(invoke_module_function(xml_string, "replace_tags"), expected)

    def test_replace_tags_strong(self):
        xml_string = b"<root><strong/></root>"
        expected = b"<root><bold /></root>"
        self.assertEqual(invoke_module_function(xml_string, "replace_tags"), expected)

    def test_replace_tags_a(self):
        xml_string = b'<root><a href="https://example.org/">Example</a></root>'
        expected = (
            b'<root xmlns:xlink="http://www.w3.org/1999/xlink">'
            b'<ext-link ext-link-type="uri" xlink:href="https://example.org/">'
            b"Example<"
            b"/ext-link>"
            b"</root>"
        )
        self.assertEqual(invoke_module_function(xml_string, "replace_tags"), expected)

    def test_replace_tags_img(self):
        xml_string = b"<root><img/></root>"
        expected = b"<root><inline-graphic /></root>"
        self.assertEqual(invoke_module_function(xml_string, "replace_tags"), expected)

    def test_replace_tags_li(self):
        xml_string = b"<root><li/></root>"
        expected = b"<root><list-item /></root>"
        self.assertEqual(invoke_module_function(xml_string, "replace_tags"), expected)

    def test_replace_tags_ol(self):
        xml_string = b"<root><ol/></root>"
        expected = b'<root><list list-type="order" /></root>'
        self.assertEqual(invoke_module_function(xml_string, "replace_tags"), expected)

    def test_replace_tags_ul(self):
        xml_string = b"<root><ul/></root>"
        expected = b'<root><list list-type="bullet" /></root>'
        self.assertEqual(invoke_module_function(xml_string, "replace_tags"), expected)


class TestRepair(unittest.TestCase):
    def test_repair_br_tag(self):
        string = "<root><p><br></p></root>"
        expected = "<root><p><br/></p></root>"
        content = convert.repair(string)
        self.assertEqual(content, expected)

    def test_repair_em_strong_mismatch(self):
        "test em strong mismatched close tags"
        string = '<root><p><em type="test"><strong>Hello!</em></strong></p></root>'
        expected = '<root><p><strong><em type="test">Hello!</em></strong></p></root>'
        content = convert.repair(string)
        self.assertEqual(content, expected)

    def test_repair_strong_em_mismatch(self):
        string = '<root><p><strong type="test"><em type="test">Hello!</strong></em></p></root>'
        expected = '<root><p><em type="test"><strong type="test">Hello!</strong></em></p></root>'
        content = convert.repair(string)
        self.assertEqual(content, expected)
