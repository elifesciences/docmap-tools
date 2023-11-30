import os
import unittest
from collections import OrderedDict
import json
from mock import patch
from docmaptools import configure_logging, LOGGER, parse
from tests.helpers import delete_files_in_folder, read_fixture, read_log_file_lines


class FakeRequest:
    def __init__(self):
        self.headers = {}
        self.body = None


class FakeResponse:
    def __init__(self, status_code, response_json=None, text="", content=None):
        self.status_code = status_code
        self.response_json = response_json
        self.content = content
        self.text = text
        self.request = FakeRequest()
        self.headers = {}

    def json(self):
        return self.response_json


class TestGetWebContent(unittest.TestCase):
    def setUp(self):
        self.temp_dir = "tests/tmp"
        self.log_file = os.path.join(self.temp_dir, "test.log")
        self.log_handler = configure_logging(self.log_file)

    def tearDown(self):
        LOGGER.removeHandler(self.log_handler)
        delete_files_in_folder(self.temp_dir, filter_out=[".keepme"])

    @patch("requests.get")
    def test_get_web_content(self, mock_get):
        mock_get.return_value = FakeResponse(
            200, content=read_fixture("sample_page.html", mode="rb")
        )
        path = "https://example.org"
        content = parse.get_web_content(path)
        self.assertTrue(isinstance(content, bytes))
        log_file_lines = read_log_file_lines(self.log_file)
        self.assertEqual(
            log_file_lines[0], "INFO docmaptools:parse:get_web_content: GET %s\n" % path
        )

    @patch("requests.get")
    def test_get_web_content_404(self, mock_get):
        mock_get.return_value = FakeResponse(
            404, content=read_fixture("sample_page.html", mode="rb")
        )
        path = "https://example.org"
        content = parse.get_web_content(path)
        self.assertEqual(content, None)
        log_file_lines = read_log_file_lines(self.log_file)
        self.assertEqual(
            log_file_lines[0], "INFO docmaptools:parse:get_web_content: GET %s\n" % path
        )
        self.assertEqual(
            log_file_lines[1],
            "INFO docmaptools:parse:get_web_content: Status code 404 for GET %s\n"
            % path,
        )


class TestDocmapJson(unittest.TestCase):
    def test_docmap_json_446694(self):
        docmap_string = read_fixture("2021.06.02.446694.docmap.json", mode="r")
        result = parse.docmap_json(docmap_string)
        # some simple assertions
        self.assertEqual(result.get("first-step"), "_:b0")
        self.assertEqual(len(result.get("steps")), 1)

    def test_docmap_json_512253(self):
        docmap_string = read_fixture("2022.10.17.512253.docmap.json", mode="r")
        result = parse.docmap_json(docmap_string)
        # some simple assertions
        self.assertEqual(result.get("first-step"), "_:b0")
        self.assertEqual(len(result.get("steps")), 3)


class TestDocmapSteps85111Sample(unittest.TestCase):
    def setUp(self):
        docmap_string = read_fixture("sample_docmap_for_85111.json", mode="r")
        self.d_json = json.loads(docmap_string)

    def test_docmap_steps(self):
        "get the steps of the docmap"
        result = parse.docmap_steps(self.d_json)
        self.assertEqual(len(result), 6)

    def test_docmap_first_step(self):
        "get the first step according to the first-step value"
        result = parse.docmap_first_step(self.d_json)

        self.assertEqual(len(result), 4)
        self.assertEqual(
            sorted(result.keys()), ["actions", "assertions", "inputs", "next-step"]
        )

    def test_step_inputs(self):
        "get inputs from the first step"
        first_step = parse.docmap_first_step(self.d_json)
        result = parse.step_inputs(first_step)
        self.assertEqual(len(result), 1)
        # step _:b1
        step_1 = parse.next_step(self.d_json, first_step)
        result = parse.step_inputs(step_1)
        self.assertEqual(len(result), 1)
        # step _:b2
        step_2 = parse.next_step(self.d_json, step_1)
        result = parse.step_inputs(step_2)
        self.assertEqual(len(result), 5)
        # step _:b3
        step_3 = parse.next_step(self.d_json, step_2)
        result = parse.step_inputs(step_3)
        self.assertEqual(len(result), 1)
        # step _:b4
        step_4 = parse.next_step(self.d_json, step_3)
        result = parse.step_inputs(step_4)
        self.assertEqual(len(result), 1)
        # step _:b5
        step_5 = parse.next_step(self.d_json, step_4)
        result = parse.step_inputs(step_5)
        self.assertEqual(len(result), 5)
        self.assertEqual(step_5.get("next-step"), None)

    def test_docmap_preprint(self):
        "preprint data from the first step inputs"
        result = parse.docmap_preprint(self.d_json)
        self.assertDictEqual(
            result,
            {
                "type": "preprint",
                "doi": "10.1101/2022.11.08.515698",
                "url": "https://www.biorxiv.org/content/10.1101/2022.11.08.515698v2",
                "versionIdentifier": "2",
                "published": "2022-11-22",
                "content": [
                    {
                        "type": "computer-file",
                        "url": "s3://transfers-elife/biorxiv_Current_Content/November_2022/23_Nov_22_Batch_1444/b0f4d90b-6c92-1014-9a2e-aae015926ab4.meca",
                    }
                ],
            },
        )

    def test_docmap_latest_preprint(self):
        "preprint data from the most recent step inputs"
        result = parse.docmap_latest_preprint(self.d_json)
        self.assertDictEqual(
            result,
            {
                "type": "preprint",
                "identifier": "85111",
                "doi": "10.7554/eLife.85111.2",
                "versionIdentifier": "2",
                "license": "http://creativecommons.org/licenses/by/4.0/",
                "published": "2023-05-10T14:00:00+00:00",
                "partOf": {
                    "type": "manuscript",
                    "doi": "10.7554/eLife.85111",
                    "identifier": "85111",
                    "subjectDisciplines": ["Neuroscience"],
                    "published": "2023-01-25T14:00:00+00:00",
                    "volumeIdentifier": "12",
                    "electronicArticleIdentifier": "RP85111",
                },
            },
        )

    def test_docmap_preprint_history(self):
        "list of preprint history event data for steps with a published date"
        result = parse.docmap_preprint_history(self.d_json)
        expected = [
            {
                "type": "preprint",
                "date": "2022-11-22",
                "doi": "10.1101/2022.11.08.515698",
                "url": "https://www.biorxiv.org/content/10.1101/2022.11.08.515698v2",
                "versionIdentifier": "2",
                "published": "2022-11-22",
                "content": [
                    {
                        "type": "computer-file",
                        "url": "s3://transfers-elife/biorxiv_Current_Content/November_2022/23_Nov_22_Batch_1444/b0f4d90b-6c92-1014-9a2e-aae015926ab4.meca",
                    }
                ],
            },
            {
                "type": "reviewed-preprint",
                "date": "2023-01-25T14:00:00+00:00",
                "identifier": "85111",
                "doi": "10.7554/eLife.85111.1",
                "versionIdentifier": "1",
                "license": "http://creativecommons.org/licenses/by/4.0/",
                "published": "2023-01-25T14:00:00+00:00",
                "partOf": {
                    "type": "manuscript",
                    "doi": "10.7554/eLife.85111",
                    "identifier": "85111",
                    "subjectDisciplines": ["Neuroscience"],
                    "published": "2023-01-25T14:00:00+00:00",
                    "volumeIdentifier": "12",
                    "electronicArticleIdentifier": "RP85111",
                },
            },
            {
                "type": "reviewed-preprint",
                "date": "2023-05-10T14:00:00+00:00",
                "identifier": "85111",
                "doi": "10.7554/eLife.85111.2",
                "versionIdentifier": "2",
                "license": "http://creativecommons.org/licenses/by/4.0/",
                "published": "2023-05-10T14:00:00+00:00",
                "partOf": {
                    "type": "manuscript",
                    "doi": "10.7554/eLife.85111",
                    "identifier": "85111",
                    "subjectDisciplines": ["Neuroscience"],
                    "published": "2023-01-25T14:00:00+00:00",
                    "volumeIdentifier": "12",
                    "electronicArticleIdentifier": "RP85111",
                },
            },
        ]
        self.assertEqual(result, expected)

    def test_preprint_review_date(self):
        "first preprint under-review date"
        result = parse.preprint_review_date(self.d_json)
        expected = "2022-11-29T14:20:30+00:00"
        self.assertEqual(result, expected)

    def test_step_actions(self):
        "get actions from the second step"
        step_2 = parse.next_step(
            self.d_json,
            parse.next_step(self.d_json, parse.docmap_first_step(self.d_json)),
        )
        result = parse.step_actions(step_2)
        self.assertEqual(len(result), 1)

    def test_action_outputs(self):
        "outputs from a step action"
        first_step = parse.docmap_first_step(self.d_json)
        first_action = parse.step_actions(first_step)[0]
        result = parse.action_outputs(first_action)
        self.assertEqual(len(result), 1)

    def test_docmap_content(self):
        "test parsing docmap JSON into docmap content structure"
        result = parse.docmap_content(self.d_json)
        expected = [
            OrderedDict(
                [
                    ("type", "review-article"),
                    ("published", "2023-04-14T13:42:24.130023+00:00"),
                    ("doi", "10.7554/eLife.85111.2.sa0"),
                    (
                        "web-content",
                        "https://sciety.org/evaluations/hypothesis:L_wlTNrKEe25pKupBGTeqA/content",
                    ),
                    (
                        "participants",
                        [
                            {
                                "actor": {"name": "anonymous", "type": "person"},
                                "role": "peer-reviewer",
                            }
                        ],
                    ),
                ]
            ),
            OrderedDict(
                [
                    ("type", "review-article"),
                    ("published", "2023-04-14T13:42:24.975810+00:00"),
                    ("doi", "10.7554/eLife.85111.2.sa1"),
                    (
                        "web-content",
                        "https://sciety.org/evaluations/hypothesis:MHuA2trKEe2NmT9GM4xGlw/content",
                    ),
                    (
                        "participants",
                        [
                            {
                                "actor": {"name": "anonymous", "type": "person"},
                                "role": "peer-reviewer",
                            }
                        ],
                    ),
                ]
            ),
            OrderedDict(
                [
                    ("type", "evaluation-summary"),
                    ("published", "2023-04-14T13:42:25.781585+00:00"),
                    ("doi", "10.7554/eLife.85111.2.sa2"),
                    (
                        "web-content",
                        "https://sciety.org/evaluations/hypothesis:MPYp6NrKEe2anmsrxlBg-w/content",
                    ),
                    (
                        "participants",
                        [
                            {
                                "actor": {
                                    "type": "person",
                                    "name": "Brice Bathellier",
                                    "firstName": "Brice",
                                    "surname": "Bathellier",
                                    "_relatesToOrganization": "CNRS, France",
                                    "affiliation": {
                                        "type": "organization",
                                        "name": "CNRS",
                                        "location": "Paris, France",
                                    },
                                },
                                "role": "editor",
                            },
                            {
                                "actor": {
                                    "type": "person",
                                    "name": "Kate Wassum",
                                    "firstName": "Kate",
                                    "_middleName": "M",
                                    "surname": "Wassum",
                                    "_relatesToOrganization": "University of California, Los Angeles, United States of America",
                                    "affiliation": {
                                        "type": "organization",
                                        "name": "University of California, Los Angeles",
                                        "location": "Los Angeles, United States of America",
                                    },
                                },
                                "role": "senior-editor",
                            },
                        ],
                    ),
                ]
            ),
            OrderedDict(
                [
                    ("type", "reply"),
                    ("published", "2023-04-20T09:20:28.046788+00:00"),
                    ("doi", "10.7554/eLife.85111.2.sa3"),
                    (
                        "web-content",
                        "https://sciety.org/evaluations/hypothesis:lxpxhN9cEe2uucduJPd1xg/content",
                    ),
                ]
            ),
        ]
        self.assertEqual(result, expected)


class TestDocmapSteps86628Sample(unittest.TestCase):
    def setUp(self):
        docmap_string = read_fixture("sample_docmap_for_86628.json", mode="r")
        self.d_json = json.loads(docmap_string)

    def test_docmap_steps(self):
        "get the steps of the docmap"
        result = parse.docmap_steps(self.d_json)
        self.assertEqual(len(result), 7)

    def test_docmap_first_step(self):
        "get the first step according to the first-step value"
        result = parse.docmap_first_step(self.d_json)

        self.assertEqual(len(result), 4)
        self.assertEqual(
            sorted(result.keys()), ["actions", "assertions", "inputs", "next-step"]
        )

    def test_step_inputs(self):
        "get inputs from the first step"
        first_step = parse.docmap_first_step(self.d_json)
        result = parse.step_inputs(first_step)
        self.assertEqual(len(result), 1)
        # step _:b1
        step_1 = parse.next_step(self.d_json, first_step)
        result = parse.step_inputs(step_1)
        self.assertEqual(len(result), 1)
        # step _:b2
        step_2 = parse.next_step(self.d_json, step_1)
        result = parse.step_inputs(step_2)
        self.assertEqual(len(result), 3)
        # step _:b3
        step_3 = parse.next_step(self.d_json, step_2)
        result = parse.step_inputs(step_3)
        self.assertEqual(len(result), 1)
        # step _:b4
        step_4 = parse.next_step(self.d_json, step_3)
        result = parse.step_inputs(step_4)
        self.assertEqual(len(result), 1)
        # step _:b5
        step_5 = parse.next_step(self.d_json, step_4)
        result = parse.step_inputs(step_5)
        self.assertEqual(len(result), 4)
        # step _:b6
        step_6 = parse.next_step(self.d_json, step_5)
        result = parse.step_inputs(step_6)
        self.assertEqual(len(result), 1)
        self.assertEqual(step_6.get("next-step"), None)

    def test_docmap_preprint(self):
        "preprint data from the first step inputs"
        result = parse.docmap_preprint(self.d_json)
        self.assertDictEqual(
            result,
            {
                "type": "preprint",
                "doi": "10.1101/2023.02.14.528498",
                "url": "https://www.biorxiv.org/content/10.1101/2023.02.14.528498v2",
                "versionIdentifier": "2",
                "published": "2023-02-21",
                "content": [
                    {
                        "type": "computer-file",
                        "url": "s3://transfers-elife/biorxiv_Current_Content/February_2023/22_Feb_23_Batch_1531/c27a22b7-6c43-1014-aa80-efc7cf011f1d.meca",
                    }
                ],
            },
        )

    def test_docmap_latest_preprint(self):
        "preprint data from the most recent step inputs"
        result = parse.docmap_latest_preprint(self.d_json)
        self.assertDictEqual(
            result,
            {
                "type": "preprint",
                "identifier": "86628",
                "doi": "10.7554/eLife.86628.2",
                "versionIdentifier": "2",
                "license": "http://creativecommons.org/licenses/by/4.0/",
                "published": "2023-05-15T14:00:00+00:00",
                "partOf": {
                    "type": "manuscript",
                    "doi": "10.7554/eLife.86628",
                    "identifier": "86628",
                    "subjectDisciplines": ["Biochemistry and Chemical Biology"],
                    "published": "2023-04-11T14:00:00+00:00",
                    "volumeIdentifier": "12",
                    "electronicArticleIdentifier": "RP86628",
                },
            },
        )

    def test_docmap_preprint_history(self):
        "list of preprint history event data"
        result = parse.docmap_preprint_history(self.d_json)
        expected = [
            {
                "type": "preprint",
                "date": "2023-02-21",
                "doi": "10.1101/2023.02.14.528498",
                "url": "https://www.biorxiv.org/content/10.1101/2023.02.14.528498v2",
                "versionIdentifier": "2",
                "published": "2023-02-21",
                "content": [
                    {
                        "type": "computer-file",
                        "url": "s3://transfers-elife/biorxiv_Current_Content/February_2023/22_Feb_23_Batch_1531/c27a22b7-6c43-1014-aa80-efc7cf011f1d.meca",
                    }
                ],
            },
            {
                "type": "reviewed-preprint",
                "date": "2023-04-11T14:00:00+00:00",
                "identifier": "86628",
                "doi": "10.7554/eLife.86628.1",
                "versionIdentifier": "1",
                "license": "http://creativecommons.org/licenses/by/4.0/",
                "published": "2023-04-11T14:00:00+00:00",
                "partOf": {
                    "type": "manuscript",
                    "doi": "10.7554/eLife.86628",
                    "identifier": "86628",
                    "subjectDisciplines": ["Biochemistry and Chemical Biology"],
                    "published": "2023-04-11T14:00:00+00:00",
                    "volumeIdentifier": "12",
                    "electronicArticleIdentifier": "RP86628",
                },
            },
            {
                "type": "reviewed-preprint",
                "date": "2023-05-15T14:00:00+00:00",
                "identifier": "86628",
                "doi": "10.7554/eLife.86628.2",
                "versionIdentifier": "2",
                "license": "http://creativecommons.org/licenses/by/4.0/",
                "published": "2023-05-15T14:00:00+00:00",
                "partOf": {
                    "type": "manuscript",
                    "doi": "10.7554/eLife.86628",
                    "identifier": "86628",
                    "subjectDisciplines": ["Biochemistry and Chemical Biology"],
                    "published": "2023-04-11T14:00:00+00:00",
                    "volumeIdentifier": "12",
                    "electronicArticleIdentifier": "RP86628",
                },
            },
        ]
        self.assertEqual(result, expected)

    def test_step_actions(self):
        "get actions from the second step"
        step_2 = parse.next_step(
            self.d_json,
            parse.next_step(self.d_json, parse.docmap_first_step(self.d_json)),
        )
        result = parse.step_actions(step_2)
        self.assertEqual(len(result), 1)

    def test_action_outputs(self):
        "outputs from a step action"
        first_step = parse.docmap_first_step(self.d_json)
        first_action = parse.step_actions(first_step)[0]
        result = parse.action_outputs(first_action)
        self.assertEqual(len(result), 1)

    def test_docmap_content(self):
        "test parsing docmap JSON into docmap content structure"
        result = parse.docmap_content(self.d_json)
        expected = [
            OrderedDict(
                [
                    ("type", "reply"),
                    ("published", "2023-05-11T11:34:27.242112+00:00"),
                    ("doi", "10.7554/eLife.86628.2.sa0"),
                    (
                        "web-content",
                        "https://sciety.org/evaluations/hypothesis:yVioUu_vEe2vQTPxYtnZSw/content",
                    ),
                ]
            ),
            OrderedDict(
                [
                    ("type", "review-article"),
                    ("published", "2023-05-11T11:34:28.135284+00:00"),
                    ("doi", "10.7554/eLife.86628.2.sa1"),
                    (
                        "web-content",
                        "https://sciety.org/evaluations/hypothesis:yeEcZO_vEe2Dxo8DxUJqTw/content",
                    ),
                    (
                        "participants",
                        [
                            {
                                "actor": {"name": "anonymous", "type": "person"},
                                "role": "peer-reviewer",
                            }
                        ],
                    ),
                ]
            ),
            OrderedDict(
                [
                    ("type", "evaluation-summary"),
                    ("published", "2023-05-11T11:34:28.903631+00:00"),
                    ("doi", "10.7554/eLife.86628.2.sa2"),
                    (
                        "web-content",
                        "https://sciety.org/evaluations/hypothesis:ylaROO_vEe2VSj_o0Xi_gA/content",
                    ),
                    (
                        "participants",
                        [
                            {
                                "actor": {
                                    "type": "person",
                                    "name": "Gary Yellen",
                                    "firstName": "Gary",
                                    "surname": "Yellen",
                                    "_relatesToOrganization": "Harvard Medical School, United States of America",
                                    "affiliation": {
                                        "type": "organization",
                                        "name": "Harvard Medical School",
                                        "location": "Boston, United States of America",
                                    },
                                },
                                "role": "editor",
                            },
                            {
                                "actor": {
                                    "type": "person",
                                    "name": "David James",
                                    "firstName": "David",
                                    "_middleName": "E",
                                    "surname": "James",
                                    "_relatesToOrganization": "University of Sydney, Australia",
                                    "affiliation": {
                                        "type": "organization",
                                        "name": "University of Sydney",
                                        "location": "Sydney, Australia",
                                    },
                                },
                                "role": "senior-editor",
                            },
                        ],
                    ),
                ]
            ),
        ]
        self.assertEqual(result, expected)


class TestDocmapPreprint(unittest.TestCase):
    def test_docmap_preprint(self):
        "test case for when there is empty input"
        self.assertEqual(parse.docmap_preprint({}), {})


class TestPreprintReviewDate(unittest.TestCase):
    "tests for parse.preprint_review_date()"

    def test_preprint_review_date(self):
        "test case for when there is empty input"
        self.assertEqual(parse.preprint_review_date({}), None)

    def test_no_assertions(self):
        "test case for steps but no assertions"
        d_json = {"first-step": "_:b0", "steps": {"_:b0": {"assertions": []}}}
        self.assertEqual(parse.preprint_review_date(d_json), None)


class TestDocmapSteps446694(unittest.TestCase):
    def setUp(self):
        docmap_string = read_fixture("2021.06.02.446694.docmap.json", mode="r")
        self.d_json = json.loads(docmap_string)

    def test_docmap_steps(self):
        "get the steps of the docmap"
        result = parse.docmap_steps(self.d_json)
        self.assertEqual(len(result), 1)

    def test_docmap_first_step(self):
        "get the first step according to the first-step value"
        result = parse.docmap_first_step(self.d_json)
        self.assertEqual(len(result), 3)
        self.assertEqual(sorted(result.keys()), ["actions", "assertions", "inputs"])

    def test_step_inputs(self):
        "get inputs from the first step"
        first_step = parse.docmap_first_step(self.d_json)
        result = parse.step_inputs(first_step)
        self.assertEqual(len(result), 1)

    def test_docmap_preprint(self):
        "preprint data from the first step inputs"
        result = parse.docmap_preprint(self.d_json)
        self.assertDictEqual(
            result,
            {
                "doi": "10.1101/2021.06.02.446694",
                "url": "https://doi.org/10.1101/2021.06.02.446694",
            },
        )

    def test_docmap_latest_preprint(self):
        "preprint data from the most recent step inputs"
        result = parse.docmap_latest_preprint(self.d_json)
        self.assertDictEqual(
            result,
            {
                "doi": "10.1101/2021.06.02.446694",
                "url": "https://doi.org/10.1101/2021.06.02.446694",
            },
        )

    def test_step_actions(self):
        "get actions from the first step"
        first_step = parse.docmap_first_step(self.d_json)
        result = parse.step_actions(first_step)
        self.assertEqual(len(result), 5)

    def test_action_outputs(self):
        "outputs from a step action"
        first_step = parse.docmap_first_step(self.d_json)
        first_action = parse.step_actions(first_step)[0]
        result = parse.action_outputs(first_action)
        self.assertEqual(len(result), 1)

    def test_docmap_content(self):
        "test parsing docmap JSON into docmap content structure"
        result = parse.docmap_content(self.d_json)
        expected = [
            OrderedDict(
                [
                    ("type", "review-article"),
                    ("published", "2022-02-15T09:43:12.593Z"),
                    ("doi", None),
                    (
                        "web-content",
                        "https://sciety.org/evaluations/hypothesis:sQ7jVo5DEeyQwX8SmvZEzw/content",
                    ),
                    (
                        "participants",
                        [
                            {
                                "actor": {"name": "anonymous", "type": "person"},
                                "role": "peer-reviewer",
                            }
                        ],
                    ),
                ]
            ),
            OrderedDict(
                [
                    ("type", "review-article"),
                    ("published", "2022-02-15T09:43:13.592Z"),
                    ("doi", None),
                    (
                        "web-content",
                        "https://sciety.org/evaluations/hypothesis:saaeso5DEeyNd5_qxlJjXQ/content",
                    ),
                    (
                        "participants",
                        [
                            {
                                "actor": {"name": "anonymous", "type": "person"},
                                "role": "peer-reviewer",
                            }
                        ],
                    ),
                ]
            ),
            OrderedDict(
                [
                    ("type", "review-article"),
                    ("published", "2022-02-15T09:43:14.350Z"),
                    ("doi", None),
                    (
                        "web-content",
                        "https://sciety.org/evaluations/hypothesis:shmDUI5DEey0T6t05fjycg/content",
                    ),
                    (
                        "participants",
                        [
                            {
                                "actor": {"name": "anonymous", "type": "person"},
                                "role": "peer-reviewer",
                            }
                        ],
                    ),
                ]
            ),
            OrderedDict(
                [
                    ("type", "evaluation-summary"),
                    ("published", "2022-02-15T09:43:15.348Z"),
                    ("doi", None),
                    (
                        "web-content",
                        "https://sciety.org/evaluations/hypothesis:srHqyI5DEeyY91tQ-MUVKA/content",
                    ),
                    (
                        "participants",
                        [
                            {
                                "actor": {
                                    "name": "Ronald L Calabrese",
                                    "type": "person",
                                    "_relatesToOrganization": "Emory University, United States",
                                },
                                "role": "senior-editor",
                            },
                            {
                                "actor": {
                                    "name": "Noah J Cowan",
                                    "type": "person",
                                    "_relatesToOrganization": "Johns Hopkins University, United States",
                                },
                                "role": "editor",
                            },
                        ],
                    ),
                ]
            ),
            OrderedDict(
                [
                    ("type", "reply"),
                    ("published", "2022-02-15T11:24:05.730Z"),
                    ("doi", None),
                    (
                        "web-content",
                        "https://sciety.org/evaluations/hypothesis:ySfx9I5REeyOiqtIYslcxA/content",
                    ),
                    (
                        "participants",
                        [
                            {
                                "actor": {"name": "anonymous", "type": "person"},
                                "role": "peer-reviewer",
                            }
                        ],
                    ),
                ]
            ),
        ]
        self.assertEqual(result, expected)

    def test_output_content(self):
        "test for all values for an output"
        output_json = {
            "type": "reply",
            "published": "2022-02-15T11:24:05.730Z",
            "content": [
                {
                    "type": "web-content",
                    "url": "https://sciety.org/evaluations/hypothesis:ySfx9I5REeyOiqtIYslcxA/content",
                }
            ],
        }
        expected = OrderedDict(
            [
                ("type", "reply"),
                ("published", "2022-02-15T11:24:05.730Z"),
                ("doi", None),
                (
                    "web-content",
                    "https://sciety.org/evaluations/hypothesis:ySfx9I5REeyOiqtIYslcxA/content",
                ),
            ]
        )
        result = parse.output_content(output_json)
        self.assertEqual(result, expected)

    def test_output_content_json_empty(self):
        "test for blank output_json"
        output_json = {}
        expected = OrderedDict(
            [
                ("type", None),
                ("published", None),
                ("doi", None),
                ("web-content", None),
            ]
        )
        result = parse.output_content(output_json)
        self.assertEqual(result, expected)

    def test_output_content_no_content(self):
        "test for content missing form the output_json"
        output_json = {"type": "reply", "published": "2022-02-15T11:24:05.730Z"}
        expected = OrderedDict(
            [
                ("type", "reply"),
                ("published", "2022-02-15T11:24:05.730Z"),
                ("doi", None),
                ("web-content", None),
            ]
        )
        result = parse.output_content(output_json)
        self.assertEqual(result, expected)


class TestDocmapSteps512253(unittest.TestCase):
    def setUp(self):
        docmap_string = read_fixture("2022.10.17.512253.docmap.json", mode="r")
        self.d_json = json.loads(docmap_string)

    def test_docmap_steps(self):
        "get the steps of the docmap"
        result = parse.docmap_steps(self.d_json)
        self.assertEqual(len(result), 3)

    def test_docmap_first_step(self):
        "get the first step according to the first-step value"
        result = parse.docmap_first_step(self.d_json)

        self.assertEqual(len(result), 4)
        self.assertEqual(
            sorted(result.keys()), ["actions", "assertions", "inputs", "next-step"]
        )

    def test_step_inputs(self):
        "get inputs from the first step"
        first_step = parse.docmap_first_step(self.d_json)
        result = parse.step_inputs(first_step)
        self.assertEqual(len(result), 0)
        # step _:b1
        step_1 = parse.next_step(self.d_json, first_step)
        result = parse.step_inputs(step_1)
        self.assertEqual(len(result), 1)
        # step _:b2
        step_2 = parse.next_step(self.d_json, step_1)
        result = parse.step_inputs(step_2)
        self.assertEqual(len(result), 1)
        self.assertEqual(step_2.get("next-step"), None)

    def test_step_assertions(self):
        "get assertions from the first step"
        first_step = parse.docmap_first_step(self.d_json)
        result = parse.step_assertions(first_step)
        self.assertEqual(len(result), 1)
        # step _:b1
        step_1 = parse.next_step(self.d_json, first_step)
        result = parse.step_assertions(step_1)
        self.assertEqual(len(result), 2)
        # step _:b2
        step_2 = parse.next_step(self.d_json, step_1)
        result = parse.step_assertions(step_2)
        self.assertEqual(len(result), 1)
        self.assertEqual(step_2.get("next-step"), None)

    def test_docmap_preprint(self):
        "preprint data from the first step inputs"
        result = parse.docmap_preprint(self.d_json)
        self.assertDictEqual(
            result,
            {
                "type": "preprint",
                "doi": "10.1101/2022.10.17.512253",
                "url": "https://www.biorxiv.org/content/10.1101/2022.10.17.512253v1",
                "published": "2022-10-17",
                "versionIdentifier": "1",
                "_tdmPath": "s3://transfers-elife/biorxiv_Current_Content/October_2022/18_Oct_22_Batch_1408/a6575018-6cfe-1014-94b3-ca3c122c1e09.meca",
            },
        )

    def test_docmap_latest_preprint(self):
        "preprint data from the most recent step inputs"
        result = parse.docmap_latest_preprint(self.d_json)
        self.assertDictEqual(
            result,
            {
                "identifier": "84364",
                "versionIdentifier": "1",
                "type": "preprint",
                "doi": "10.7554/eLife.84364.1",
            },
        )

    def test_docmap_preprint_history(self):
        "list of preprint history event data"
        result = parse.docmap_preprint_history(self.d_json)
        expected = [
            {
                "type": "preprint",
                "date": "2022-10-17",
                "doi": "10.1101/2022.10.17.512253",
                "url": "https://www.biorxiv.org/content/10.1101/2022.10.17.512253v1",
                "published": "2022-10-17",
                "versionIdentifier": "1",
                "_tdmPath": "s3://transfers-elife/biorxiv_Current_Content/October_2022/18_Oct_22_Batch_1408/a6575018-6cfe-1014-94b3-ca3c122c1e09.meca",
            },
        ]
        self.assertEqual(result, expected)

    def test_step_actions(self):
        "get actions from the last step"
        step_2 = parse.next_step(
            self.d_json,
            parse.next_step(self.d_json, parse.docmap_first_step(self.d_json)),
        )
        result = parse.step_actions(step_2)
        self.assertEqual(len(result), 4)

    def test_action_outputs(self):
        "outputs from a step action"
        first_step = parse.docmap_first_step(self.d_json)
        first_action = parse.step_actions(first_step)[0]
        result = parse.action_outputs(first_action)
        self.assertEqual(len(result), 1)

    def test_docmap_content(self):
        "test parsing docmap JSON into docmap content structure"
        result = parse.docmap_content(self.d_json)
        expected = [
            OrderedDict(
                [
                    ("type", "review-article"),
                    ("published", "2023-02-09T16:36:07.240248+00:00"),
                    ("doi", "10.7554/eLife.84364.1.sa1"),
                    (
                        "web-content",
                        "https://sciety.org/evaluations/hypothesis:2jRPwqiXEe2WiaPpkX9z0A/content",
                    ),
                    (
                        "participants",
                        [
                            {
                                "actor": {"name": "anonymous", "type": "person"},
                                "role": "peer-reviewer",
                            }
                        ],
                    ),
                ]
            ),
            OrderedDict(
                [
                    ("type", "review-article"),
                    ("published", "2023-02-09T16:36:08.237709+00:00"),
                    ("doi", "10.7554/eLife.84364.1.sa2"),
                    (
                        "web-content",
                        "https://sciety.org/evaluations/hypothesis:2ssR5qiXEe2eBA-GlPB-OA/content",
                    ),
                    (
                        "participants",
                        [
                            {
                                "actor": {"name": "anonymous", "type": "person"},
                                "role": "peer-reviewer",
                            }
                        ],
                    ),
                ]
            ),
            OrderedDict(
                [
                    ("type", "review-article"),
                    ("published", "2023-02-09T16:36:09.046089+00:00"),
                    ("doi", "10.7554/eLife.84364.1.sa3"),
                    (
                        "web-content",
                        "https://sciety.org/evaluations/hypothesis:20aozqiXEe2cFHOdrUiwoQ/content",
                    ),
                    (
                        "participants",
                        [
                            {
                                "actor": {"name": "anonymous", "type": "person"},
                                "role": "peer-reviewer",
                            }
                        ],
                    ),
                ]
            ),
            OrderedDict(
                [
                    ("type", "evaluation-summary"),
                    ("published", "2023-02-09T16:36:09.857359+00:00"),
                    ("doi", "10.7554/eLife.84364.1.sa4"),
                    (
                        "web-content",
                        "https://sciety.org/evaluations/hypothesis:28TBAKiXEe2gLa-4_Zmg3Q/content",
                    ),
                    (
                        "participants",
                        [
                            {
                                "actor": {
                                    "name": "Michael Eisen",
                                    "type": "person",
                                    "_relatesToOrganization": "University of California, Berkeley, United States of America",
                                },
                                "role": "editor",
                            },
                            {
                                "actor": {
                                    "name": "Michael Eisen",
                                    "type": "person",
                                    "_relatesToOrganization": "University of California, Berkeley, United States of America",
                                },
                                "role": "senior-editor",
                            },
                        ],
                    ),
                ]
            ),
        ]
        self.assertEqual(result, expected)


class TestPreprintEventOutput(unittest.TestCase):
    def setUp(self):
        self.output_type = "preprint"
        self.output_doi = "10.7554/eLife.85111.1"
        self.output_version_identifier = "1"
        self.output_date_string = "2023-04-27T15:30:00+00:00"
        self.step_json = {
            "assertions": [
                {
                    "status": "manuscript-published",
                    "happened": self.output_date_string,
                    "item": {"type": "preprint"},
                }
            ]
        }

    def test_not_found(self):
        "test if first preprint is not yet found"
        found_first_preprint = False
        output_json = {
            "type": self.output_type,
            "doi": self.output_doi,
            "versionIdentifier": self.output_version_identifier,
            "published": self.output_date_string,
        }
        expected = {
            "type": self.output_type,
            "date": self.output_date_string,
            "doi": self.output_doi,
            "versionIdentifier": self.output_version_identifier,
            "published": self.output_date_string,
        }
        result = parse.preprint_event_output(
            output_json, self.step_json, found_first_preprint
        )
        self.assertDictEqual(result, expected)

    def test_found(self):
        "test if first preprint is already found"
        found_first_preprint = True
        output_json = {
            "type": self.output_type,
            "doi": self.output_doi,
            "versionIdentifier": self.output_version_identifier,
            "date": self.output_date_string,
        }
        expected = {
            "type": "reviewed-preprint",
            "doi": self.output_doi,
            "versionIdentifier": self.output_version_identifier,
            "date": self.output_date_string,
        }
        result = parse.preprint_event_output(
            output_json, self.step_json, found_first_preprint
        )
        self.assertDictEqual(result, expected)


class TestDocmapLatestPreprint(unittest.TestCase):
    def test_docmap_latest_preprint_empty(self):
        "test for if d_json is empty"
        result = parse.docmap_latest_preprint({})
        self.assertEqual(result, {})


class TestPreprintHappenedDate(unittest.TestCase):
    def test_preprint_happened_date(self):
        date_string = "2023-04-27T15:30:00+00:00"
        step_json = {
            "assertions": [
                {
                    "status": "manuscript-published",
                    "happened": date_string,
                    "item": {"type": "preprint"},
                }
            ]
        }
        self.assertEqual(parse.preprint_happened_date(step_json), date_string)

    def test_revised_preprint_happened_date(self):
        "the data may have revised instead of manuscript-published"
        date_string = "2023-04-27T15:30:00+00:00"
        step_json = {
            "assertions": [
                {
                    "status": "revised",
                    "happened": date_string,
                    "item": {"type": "preprint"},
                }
            ]
        }
        self.assertEqual(parse.preprint_happened_date(step_json), date_string)

    def test_none(self):
        step_json = None
        self.assertEqual(parse.preprint_happened_date(step_json), None)


class TestPreprintReviewHappenedDate(unittest.TestCase):
    "tests for parse.preprint_review_happened_date()"

    def test_happened_date(self):
        "test returning a happened date"
        date_string = "2023-04-27T15:30:00+00:00"
        step_json = {
            "assertions": [
                {
                    "status": "under-review",
                    "happened": date_string,
                    "item": {"type": "preprint"},
                }
            ]
        }
        self.assertEqual(parse.preprint_review_happened_date(step_json), date_string)

    def test_none(self):
        "test if there is no step data"
        step_json = None
        self.assertEqual(parse.preprint_review_happened_date(step_json), None)


class TestPreprintAlternateDate(unittest.TestCase):
    def test_preprint_alternate_date(self):
        date_string = "2023-04-27T15:30:00+00:00"
        step_json = {
            "actions": [
                {
                    "outputs": [
                        {
                            "type": "preprint",
                            "published": date_string,
                        }
                    ]
                }
            ]
        }
        self.assertEqual(parse.preprint_alternate_date(step_json), date_string)

    def test_no_outputs(self):
        step_json = {"actions": [{"outputs": []}]}
        self.assertEqual(parse.preprint_alternate_date(step_json), None)

    def test_none(self):
        step_json = None
        self.assertEqual(parse.preprint_alternate_date(step_json), None)


class TestContentStep(unittest.TestCase):
    def test_content_step_none(self):
        d_json = None
        self.assertEqual(parse.content_step(d_json), None)

    def test_content_step_empty(self):
        d_json = {}
        self.assertEqual(parse.content_step(d_json), None)

    def test_content_step_missing(self):
        content_step = {"actions": [{"outputs": [{"type": "no-match"}]}]}
        d_json = {"first-step": "_:b0", "steps": {"_:b0": content_step}}
        self.assertEqual(parse.content_step(d_json), None)

    def test_content_step(self):
        content_step = {"actions": [{"outputs": [{"type": "review-article"}]}]}
        d_json = {"first-step": "_:b0", "steps": {"_:b0": content_step}}
        self.assertEqual(parse.content_step(d_json), content_step)

    def test_sample(self):
        "test a more complete docmap with no doi argument"
        doi = None
        expected_previous_step = "_:b3"
        docmap_string = read_fixture("sample_docmap_for_85111.json", mode="r")
        d_json = json.loads(docmap_string)
        self.assertEqual(
            parse.content_step(d_json, doi).get("previous-step"), expected_previous_step
        )

    def test_sample_doi(self):
        "test when doi argument is specified"
        doi = "10.7554/eLife.85111.1"
        expected_previous_step = "_:b0"
        docmap_string = read_fixture("sample_docmap_for_85111.json", mode="r")
        d_json = json.loads(docmap_string)
        self.assertEqual(
            parse.content_step(d_json, doi).get("previous-step"), expected_previous_step
        )


class TestPopulateDocmapContent(unittest.TestCase):
    def setUp(self):
        docmap_string = read_fixture("2021.06.02.446694.docmap.json", mode="r")
        d_json = json.loads(docmap_string)
        self.content_json = parse.docmap_content(d_json)

    @patch("requests.get")
    def test_populate_docmap_content(self, mock_get):
        html_content = b"<p><strong>Author Response:</strong></p>"
        mock_get.return_value = FakeResponse(200, content=html_content)
        result = parse.populate_docmap_content(self.content_json)
        self.assertEqual(result[0]["html"], html_content)

    @patch("requests.get")
    def test_404(self, mock_get):
        mock_get.return_value = FakeResponse(404)
        result = parse.populate_docmap_content(self.content_json)
        self.assertEqual(result[0]["html"], None)

    @patch("requests.get")
    def test_exception(self, mock_get):
        mock_get.side_effect = Exception("An exception")
        with self.assertRaises(Exception):
            parse.populate_docmap_content(self.content_json)


class TestTransformDocmapContent(unittest.TestCase):
    def setUp(self):
        self.temp_dir = "tests/tmp"
        self.log_file = os.path.join(self.temp_dir, "test.log")
        self.log_handler = configure_logging(self.log_file)

    def tearDown(self):
        LOGGER.removeHandler(self.log_handler)
        delete_files_in_folder(self.temp_dir, filter_out=[".keepme"])

    def test_transform_docmap_content(self):
        content_json = [
            OrderedDict(
                [
                    ("type", "review-article"),
                    ("published", "2022-02-15T09:43:12.593Z"),
                    (
                        "web-content",
                        "https://sciety.org/evaluations/hypothesis:sQ7jVo5DEeyQwX8SmvZEzw/content",
                    ),
                    (
                        "html",
                        b"<p><strong>Reviewer #3 (Public Review):</strong></p>\n<p>The ....</p>\n",
                    ),
                ]
            ),
        ]
        xml_expected = (
            b"<root><front-stub><title-group><article-title>"
            b"Reviewer #3 (Public Review):"
            b"</article-title></title-group>\n</front-stub>"
            b"<body><p>The ....</p>\n</body>"
            b"</root>"
        )
        result = parse.transform_docmap_content(content_json)
        self.assertEqual(result[0].get("xml"), xml_expected)

    def test_parseerror_exception(self):
        "test a failure to convert HTML to XML"
        content_json = [
            OrderedDict(
                [
                    ("type", "review-article"),
                    ("published", "2022-02-15T09:43:12.593Z"),
                    (
                        "web-content",
                        "https://sciety.org/evaluations/hypothesis:sQ7jVo5DEeyQwX8SmvZEzw/content",
                    ),
                    (
                        "html",
                        b"<p>Unmatched tag",
                    ),
                ]
            ),
        ]
        xml_expected = None

        result = parse.transform_docmap_content(content_json)
        self.assertEqual(result[0].get("xml"), xml_expected)

        log_file_lines = read_log_file_lines(self.log_file)
        self.assertEqual(
            log_file_lines[0],
            "ERROR docmaptools:parse:transform_docmap_content: Failed to convert HTML to XML\n",
        )
        self.assertEqual(log_file_lines[1], "Traceback (most recent call last):\n")
        self.assertTrue(
            log_file_lines[-1].startswith(
                "xml.etree.ElementTree.ParseError: mismatched tag:"
            )
        )

    @patch("docmaptools.convert.convert_html_string")
    def test_unhandled_exception(self, mock_convert_html_string):
        "test for an unhandled exception"
        content_json = [
            OrderedDict(
                [
                    ("type", "review-article"),
                    ("published", "2022-02-15T09:43:12.593Z"),
                    (
                        "web-content",
                        "https://sciety.org/evaluations/hypothesis:sQ7jVo5DEeyQwX8SmvZEzw/content",
                    ),
                    (
                        "html",
                        b"<p/>",
                    ),
                ]
            ),
        ]
        mock_convert_html_string.side_effect = Exception("Unhandled exception")
        with self.assertRaises(Exception):
            parse.transform_docmap_content(content_json)

        log_file_lines = read_log_file_lines(self.log_file)
        self.assertEqual(
            log_file_lines[0],
            "ERROR docmaptools:parse:transform_docmap_content: Unhandled exception\n",
        )
        self.assertEqual(log_file_lines[1], "Traceback (most recent call last):\n")
