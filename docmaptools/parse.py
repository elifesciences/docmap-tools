from collections import OrderedDict
import json
from xml.etree.ElementTree import ParseError
import requests
from docmaptools import convert, LOGGER


def get_web_content(path):
    "HTTP get request for the path and return content"
    request = requests.get(path)
    LOGGER.info("GET %s", path)
    if request.status_code == 200:
        return request.content
    LOGGER.info("Status code %s for GET %s", request.status_code, path)
    return None


def docmap_json(docmap_string):
    "parse docmap JSON"
    return json.loads(docmap_string)


def docmap_steps(d_json):
    "docmap steps"
    return d_json.get("steps")


def docmap_first_step(d_json):
    "find and return the first step of the docmap"
    first_step_index = d_json.get("first-step")
    return docmap_steps(d_json).get(first_step_index)


def step_inputs(step_json):
    "return the inputs of the step"
    return step_json.get("inputs")


def docmap_preprint(d_json):
    "assume the preprint data is the first step first inputs value"
    first_step = docmap_first_step(d_json)
    return step_inputs(first_step)[0]


def step_actions(step_json):
    "return the actions of the step"
    return step_json.get("actions")


def action_outputs(action_json):
    "return the outputs of an action"
    return action_json.get("outputs")


def output_content(output_json):
    "extract web-content and metadata from an output"
    content_item = OrderedDict()
    content_item["type"] = output_json.get("type")
    content_item["published"] = output_json.get("published")
    web_content = [
        content.get("url", {})
        for content in output_json.get("content", [])
        if content.get("type") == "web-content"
    ]
    # use the first web-content for now
    content_item["web-content"] = web_content[0] if len(web_content) >= 1 else None
    return content_item


def action_content(action_json):
    "extract web-content and metadata from an action"
    outputs = action_outputs(action_json)
    # look at the first item in the list for now
    return output_content(outputs[0])


def docmap_content(d_json):
    "abbreviated and simplified data for content outputs"
    content = []
    # the step from which to get the data
    step = docmap_first_step(d_json)
    # the actions
    actions = step_actions(step)
    # loop through the outputs
    for action in actions:
        content.append(action_content(action))
    return content


def populate_docmap_content(content_json):
    "get web-content url content and add the HTML to the data structure"
    for content_item in content_json:
        if content_item.get("web-content"):
            content_item["html"] = get_web_content(content_item.get("web-content"))
    return content_json


def transform_docmap_content(content_json):
    "convert HTML in web-content to XML and add it to the data structure"
    for content_item in content_json:
        if content_item.get("html"):
            try:
                content_item["xml"] = convert.convert_html_string(
                    content_item.get("html")
                )
            except ParseError:
                LOGGER.exception("Failed to convert HTML to XML")
            except:
                LOGGER.exception("Unhandled exception")
                raise
    return content_json
