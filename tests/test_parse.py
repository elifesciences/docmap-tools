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
        self.assertEqual(len(result), 5)

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
        # step _:b3
        step_3 = parse.next_step(self.d_json, step_2)
        result = parse.step_inputs(step_3)
        self.assertEqual(len(result), 0)
        # step _:b4
        step_4 = parse.next_step(self.d_json, step_3)
        result = parse.step_inputs(step_4)
        self.assertEqual(len(result), 5)
        self.assertEqual(step_4.get("next-step"), None)

    def test_docmap_preprint(self):
        "preprint data from the first step inputs"
        result = parse.docmap_preprint(self.d_json)
        self.assertDictEqual(
            result,
            {
                "type": "preprint",
                "doi": "10.1101/2022.11.08.515698",
                "url": "https://www.biorxiv.org/content/10.1101/2022.11.08.515698v2",
                "published": "2022-11-22",
                "versionIdentifier": "2",
                "_tdmPath": "s3://transfers-elife/biorxiv_Current_Content/November_2022/23_Nov_22_Batch_1444/b0f4d90b-6c92-1014-9a2e-aae015926ab4.meca",
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
                "versionIdentifier": "2",
                "doi": "10.7554/eLife.85111.2",
            },
        )

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
                [("type", "preprint"), ("published", None), ("web-content", None)]
            ),
            OrderedDict(
                [
                    ("type", "review-article"),
                    ("published", "2023-04-14T13:42:24.130023+00:00"),
                    (
                        "web-content",
                        "https://sciety.org/evaluations/hypothesis:L_wlTNrKEe25pKupBGTeqA/content",
                    ),
                ]
            ),
            OrderedDict(
                [
                    ("type", "review-article"),
                    ("published", "2023-04-14T13:42:24.975810+00:00"),
                    (
                        "web-content",
                        "https://sciety.org/evaluations/hypothesis:MHuA2trKEe2NmT9GM4xGlw/content",
                    ),
                ]
            ),
            OrderedDict(
                [
                    ("type", "evaluation-summary"),
                    ("published", "2023-04-14T13:42:25.781585+00:00"),
                    (
                        "web-content",
                        "https://sciety.org/evaluations/hypothesis:MPYp6NrKEe2anmsrxlBg-w/content",
                    ),
                ]
            ),
        ]
        self.assertEqual(result, expected)


class TestDocmapPreprint(unittest.TestCase):
    def test_docmap_preprint(self):
        "test case for when there is empty input"
        self.assertEqual(parse.docmap_preprint({}), {})


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
                    (
                        "web-content",
                        "https://sciety.org/evaluations/hypothesis:sQ7jVo5DEeyQwX8SmvZEzw/content",
                    ),
                ]
            ),
            OrderedDict(
                [
                    ("type", "review-article"),
                    ("published", "2022-02-15T09:43:13.592Z"),
                    (
                        "web-content",
                        "https://sciety.org/evaluations/hypothesis:saaeso5DEeyNd5_qxlJjXQ/content",
                    ),
                ]
            ),
            OrderedDict(
                [
                    ("type", "review-article"),
                    ("published", "2022-02-15T09:43:14.350Z"),
                    (
                        "web-content",
                        "https://sciety.org/evaluations/hypothesis:shmDUI5DEey0T6t05fjycg/content",
                    ),
                ]
            ),
            OrderedDict(
                [
                    ("type", "evaluation-summary"),
                    ("published", "2022-02-15T09:43:15.348Z"),
                    (
                        "web-content",
                        "https://sciety.org/evaluations/hypothesis:srHqyI5DEeyY91tQ-MUVKA/content",
                    ),
                ]
            ),
            OrderedDict(
                [
                    ("type", "reply"),
                    ("published", "2022-02-15T11:24:05.730Z"),
                    (
                        "web-content",
                        "https://sciety.org/evaluations/hypothesis:ySfx9I5REeyOiqtIYslcxA/content",
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
                "versionIdentifier": "",
                "type": "preprint",
                "doi": "10.7554/eLife.84364",
            },
        )

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
                    (
                        "web-content",
                        "https://sciety.org/evaluations/hypothesis:2jRPwqiXEe2WiaPpkX9z0A/content",
                    ),
                ]
            ),
            OrderedDict(
                [
                    ("type", "review-article"),
                    ("published", "2023-02-09T16:36:08.237709+00:00"),
                    (
                        "web-content",
                        "https://sciety.org/evaluations/hypothesis:2ssR5qiXEe2eBA-GlPB-OA/content",
                    ),
                ]
            ),
            OrderedDict(
                [
                    ("type", "review-article"),
                    ("published", "2023-02-09T16:36:09.046089+00:00"),
                    (
                        "web-content",
                        "https://sciety.org/evaluations/hypothesis:20aozqiXEe2cFHOdrUiwoQ/content",
                    ),
                ]
            ),
            OrderedDict(
                [
                    ("type", "evaluation-summary"),
                    ("published", "2023-02-09T16:36:09.857359+00:00"),
                    (
                        "web-content",
                        "https://sciety.org/evaluations/hypothesis:28TBAKiXEe2gLa-4_Zmg3Q/content",
                    ),
                ]
            ),
        ]
        self.assertEqual(result, expected)


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
