import re
from xml.etree import ElementTree
from xml.etree.ElementTree import Element, ParseError
from elifetools import xmlio


def convert_html_string(bytes_string):
    "convert HTML string to XML for a sub article"
    root = html_string_to_element(bytes_string)

    # convert to XML
    html_to_xml(root)

    # convert back to string
    xml_string = ElementTree.tostring(root)
    return xml_string


def html_string_to_element(bytes_string):
    "parse an HTML string to Element"
    string = bytes_string.decode("utf-8")

    # register XML namespaces
    xmlio.register_xmlns()

    # convert to XML
    string = "<root>%s</root>" % string
    try:
        root = ElementTree.fromstring(string)
    except ParseError:
        root = ElementTree.fromstring(repair(string))

    return root


def html_to_xml(root):
    "convert HTML ElementTree to JATS XML"

    # replace tags
    replace_tags(root)

    # convert blockquote tags
    blockquote_tags(root)

    # create article-title tag
    article_title_tag(root)

    # wrap in front-stub tag
    front_stub_tag(root)

    # wrap content in body tag
    body_tag(root)


def replace_tags(root):
    "rename HTML tags to XML tags"
    for elem in root.findall(".//em"):
        elem.tag = "italic"
    for elem in root.findall(".//strong"):
        elem.tag = "bold"
    for elem in root.findall(".//a"):
        elem.tag = "ext-link"
        if elem.get("href"):
            elem.set("ext-link-type", "uri")
            elem.set("{http://www.w3.org/1999/xlink}href", elem.get("href"))
            del elem.attrib["href"]
    for parent_elem in root.findall(".//img/.."):
        # add img placeholder text
        parent_elem.text = " ".join(
            [string.lstrip() for string in ["[image]", parent_elem.text] if string]
        )
        # remove img tag
        elem = parent_elem.find("img")
        parent_elem.remove(elem)
    for elem in root.findall(".//li"):
        elem.tag = "list-item"
    for elem in root.findall(".//ol"):
        elem.tag = "list"
        elem.set("list-type", "order")
    for elem in root.findall(".//ul"):
        elem.tag = "list"
        elem.set("list-type", "bullet")


def blockquote_tags(root):
    "convert blockquote tags into disp-quote tags and merge consecutive ones"
    prev_elem = None
    for elem in root.findall("*"):
        if elem.tag == "blockquote":
            if prev_elem is None or prev_elem.tag != "disp-quote":
                elem.tag = "disp-quote"
                elem.set("content-type", "editor-comment")
                prev_elem = elem
            elif prev_elem.tag == "disp-quote":
                for elem_elem in elem.findall("*"):
                    prev_elem.append(elem_elem)
                    elem.remove(elem_elem)
                root.remove(elem)
        else:
            prev_elem = elem


def article_title_tag(root):
    "convert first bold p tag into an article-title"
    elem = root.find("p")
    if elem and not elem.text:
        next_elem = elem.find("*")
        if next_elem is not None and next_elem.tag == "bold":
            # convert the tags
            elem.tag = "title-group"
            next_elem.tag = "article-title"


def front_stub_tag(root):
    "wrap title-group in a front-stub tag"
    title_group_elem = root.find("title-group")
    if title_group_elem is None:
        return
    insert_index = 1 if title_group_elem is not None else 0
    front_stub_elem = Element("front-stub")
    root.insert(insert_index, front_stub_elem)
    front_stub_elem.append(title_group_elem)
    root.remove(title_group_elem)


def body_tag(root):
    "wrap non-title content in a body tag"
    # look for a front-stub tag for where to insert the body tag
    front_stub_elem = root.find("front-stub")
    insert_index = 1 if front_stub_elem is not None else 0
    body_elem = Element("body")
    root.insert(insert_index, body_elem)
    # move top level non-body non-front-stub elements into the body
    for elem in root.findall("*"):
        if elem.tag in ["body", "front-stub"]:
            continue
        body_elem.append(elem)
        root.remove(elem)


def repair(string):
    "modify an XML string to be parsed without error"
    # replace tags with no close slash
    string = string.replace("<br>", "<br/>")
    # replace mismatched tags due to close tag order
    em_strong_tag_order_pattern = re.compile(
        r"<(em.*?)><(strong.*?)>(.*?</em></strong>)"
    )
    string = em_strong_tag_order_pattern.sub(r"<\2><\1>\3", string)
    strong_em_tag_order_pattern = re.compile(
        r"<(strong.*?)><(em.*?)>(.*?</strong></em>)"
    )
    string = strong_em_tag_order_pattern.sub(r"<\2><\1>\3", string)
    return string
