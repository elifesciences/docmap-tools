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
    return d_json.get("steps") if d_json else {}


def docmap_first_step(d_json):
    "find and return the first step of the docmap"
    first_step_index = d_json.get("first-step") if d_json else None
    return docmap_steps(d_json).get(first_step_index)


def next_step(d_json, step_json):
    "find and return the next step after the given step_json"
    return docmap_steps(d_json).get(step_json.get("next-step"))


def step_inputs(step_json):
    "return the inputs of the step"
    return step_json.get("inputs")


def step_assertions(step_json):
    "return the assertions of the step"
    return step_json.get("assertions")


def docmap_preprint(d_json):
    "find the first preprint in the docmap"
    first_step = docmap_first_step(d_json)
    if first_step and first_step.get("inputs"):
        # assume the preprint data is the first step first inputs value
        return step_inputs(first_step)[0]
    elif first_step and not first_step.get("inputs"):
        # expect to find the preprint in the first step outputs
        actions = step_actions(first_step)
        for action in actions:
            outputs = action_outputs(action)
            for output in outputs:
                if output.get("type") == "preprint":
                    return output
    return {}


def docmap_latest_preprint(d_json, published=True):
    "find the most recent preprint in the docmap"
    step = docmap_first_step(d_json)
    most_recent_output = {}
    if step:
        if step and step.get("inputs") and len(docmap_steps(d_json)) == 1:
            # assume the preprint data is the first step first inputs value
            most_recent_output = step_inputs(step)[0]
        # continue to search
        step = next_step(d_json, step)
        while step:
            actions = step_actions(step)
            for action in actions:
                outputs = action_outputs(action)
                for output in outputs:
                    if output.get("type") == "preprint":
                        if published and output.get("published"):
                            # remember this value
                            most_recent_output = output
                        elif not published:
                            # remember this value
                            most_recent_output = output
            # search the next step
            step = next_step(d_json, step)
    return most_recent_output


def docmap_preprint_output(d_json, version_doi=None, published=False):
    "return latest preprint output, optionally matching the version_doi"
    if not version_doi:
        return docmap_latest_preprint(d_json, published)
    else:
        output = None
        step_map = preprint_version_doi_step_map(d_json)
        for step_json in step_map.get(version_doi, []):
            for action_json in step_actions(step_json):
                for output_json in action_outputs(action_json):
                    if output_json.get("type") == "preprint":
                        output = output_json
    return output


def docmap_preprint_history(d_json):
    "return a list of events in a preprint publication history from the docmap"
    step_json = docmap_first_step(d_json)
    preprint_events = []
    found_first_preprint = False
    # add preprint first
    if docmap_preprint(d_json):
        # collect the preprint details
        event_details = preprint_event_output(
            docmap_preprint(d_json), step_json, found_first_preprint
        )
        # append the events details to the matser list
        preprint_events.append(event_details)
        found_first_preprint = True
    while step_json:
        for action_json in step_actions(step_json):
            for output_json in action_outputs(action_json):
                if output_json.get("type") == "preprint":
                    # decide whether to record this step
                    if not output_json.get("identifier") and found_first_preprint:
                        continue
                    # collect the preprint details
                    event_details = preprint_event_output(
                        output_json, step_json, found_first_preprint
                    )
                    # append the events details to the matser list
                    if event_details.get("date"):
                        preprint_events.append(event_details)

                    # will have found the preprint from the first matched step
                    found_first_preprint = True
        # search the next step
        step_json = next_step(d_json, step_json)
    return preprint_events


def preprint_review_date(d_json):
    "review date for the first preprint taken from assertions data"
    step_json = docmap_first_step(d_json)
    if not step_json:
        return None
    while step_json:
        if preprint_review_happened_date(step_json):
            return preprint_review_happened_date(step_json)
        # search the next step
        step_json = next_step(d_json, step_json)
    return None


def preprint_event_output(output_json, step_json, found_first_preprint):
    "collect preprint event data from the output and step actions"
    event_details = {}
    # set the type
    if found_first_preprint:
        event_details["type"] = "reviewed-preprint"
    else:
        event_details["type"] = "preprint"
    # set the date
    if found_first_preprint:
        event_details["date"] = preprint_happened_date(step_json)
        if not event_details.get("date"):
            event_details["date"] = preprint_alternate_date(step_json)
    else:
        event_details["date"] = output_json.get("published")
    # copy over additional properties
    for key in [key for key in output_json.keys() if key not in ["type"]]:
        event_details[key] = output_json.get(key)
    return event_details


def preprint_assertion_happened_date(step_json, status):
    "happened date from a preprint step assertions of status"
    # look at assertions
    if not step_json or not step_assertions(step_json):
        return None
    for assertion in step_assertions(step_json):
        if (
            assertion.get("status") == status
            and assertion.get("happened")
            and assertion.get("item")
            and assertion.get("item").get("type") == "preprint"
        ):
            return assertion.get("happened")
    return None


def preprint_happened_date(step_json):
    "happened date from a preprint assertion of status manuscript-published"
    happened = preprint_assertion_happened_date(step_json, "manuscript-published")
    if not happened:
        happened = preprint_assertion_happened_date(step_json, "revised")
    return happened


def preprint_review_happened_date(step_json):
    "happened date from a preprint assertion of status under-review"
    return preprint_assertion_happened_date(step_json, "under-review")


def preprint_alternate_date(step_json):
    "date for a preprint from its step outputs when no happened date is available"
    # if no date is yet found, look at other action output
    if not step_json or not step_actions(step_json):
        return None
    for action_json in step_actions(step_json):
        for output_json in action_outputs(action_json):
            if output_json.get("published") and output_json.get("type") == "preprint":
                return output_json.get("published")
    return None


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
    content_item["doi"] = output_json.get("doi")
    web_content = [
        content.get("url", {})
        for content in output_json.get("content", [])
        if content.get("url").endswith("/content")
    ]
    # use the first web-content for now
    content_item["web-content"] = web_content[0] if len(web_content) >= 1 else None
    return content_item


def output_partof(output_json):
    "return the partOf data from output"
    return output_json.get("partOf", {}) if output_json else {}


def action_content(action_json):
    "extract web-content and metadata from an action"
    outputs = action_outputs(action_json)
    # look at the first item in the list for now
    return output_content(outputs[0])


def content_step(d_json, doi=None):
    "find the step which includes peer review content data"
    step = docmap_first_step(d_json)
    step_previous = None
    while step:
        actions = step_actions(step)
        for action in actions:
            outputs = action_outputs(action)
            for output in outputs:
                if output.get("type") == "review-article":
                    if doi and output.get("doi") and output.get("doi").startswith(doi):
                        return step
                    # remember this step
                    step_previous = step
        # search the next step
        step = next_step(d_json, step)
    return step_previous


def docmap_content(d_json, doi=None):
    "abbreviated and simplified data for content outputs"
    content = []
    # the step from which to get the data
    step = content_step(d_json, doi)
    # the actions
    actions = step_actions(step)
    # loop through the outputs
    for action in actions:
        content_json = action_content(action)
        if action.get("participants"):
            content_json["participants"] = action.get("participants")
        content.append(content_json)
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


def preprint_version_doi_step_map(d_json):
    "preprint steps grouped by version doi"
    doi_step_map = OrderedDict()
    steps = docmap_steps(d_json)

    current_doi = None
    current_output_type = None
    for step_key in steps:
        # the actions
        actions = step_actions(steps.get(step_key))
        # loop through the outputs
        for action in actions:
            # get the output type when a particular type is in the step output
            output_type = None
            outputs = action_outputs(action)
            for output in outputs:
                if output.get("type") in ["preprint", "version-of-record"]:
                    output_type = output.get("type")
                    current_output_type = output_type

            # get the DOI key for the step depending on the type and if the DOI value is new
            content_json = action_content(action)
            if (
                content_json.get("doi")
                and output_type == "preprint"
                and content_json.get("doi") not in doi_step_map.keys()
            ):
                doi_step_map[content_json.get("doi")] = []
                current_doi = content_json.get("doi")

        # add steps that are associated only with a preprint step
        if current_output_type == "preprint":
            doi_step_map[current_doi].append(steps.get(step_key))

    return doi_step_map


def preprint_license(d_json, version_doi=None, identifier=None):
    "parse preprint license, optionally matching the version_doi"
    output_json = docmap_preprint_output(d_json, version_doi)
    return output_json.get("license")


def preprint_partof_field(d_json, field_name, version_doi=None, identifier=None):
    "return a value from the partOf data"
    # find the latest output json, optionally matching the version_doi
    output_json = docmap_preprint_output(d_json, version_doi)
    # get value from output partOf
    field_value = output_partof(output_json).get(field_name)
    if not field_value:
        LOGGER.warning("%s no %s found in the docmap", identifier, field_name)
        return None
    return field_value


def preprint_electronic_article_identifier(d_json, version_doi=None, identifier=None):
    "from the docmap get the elocation-id, optionally matching the version_doi"
    return preprint_partof_field(
        d_json, "electronicArticleIdentifier", version_doi, identifier
    )


def preprint_volume(d_json, version_doi=None, identifier=None):
    "from the docmap get the volume, optionally matching the version_doi"
    return preprint_partof_field(d_json, "volumeIdentifier", version_doi, identifier)


def preprint_subject_disciplines(d_json, version_doi=None, identifier=None):
    "from the docmap get the article categories, optionally matching the version_doi"
    return preprint_partof_field(d_json, "subjectDisciplines", version_doi, identifier)
