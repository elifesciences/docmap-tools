import os
import unittest
from docmaptools import configure_logging, LOGGER
from tests.helpers import delete_files_in_folder


class TestInit(unittest.TestCase):
    def setUp(self):
        self.temp_dir = "tests/tmp"
        self.log_file = os.path.join(self.temp_dir, "test.log")

    def tearDown(self):
        delete_files_in_folder(self.temp_dir, filter_out=[".keepme"])

    def test_configure_logging(self):
        expected = "INFO docmaptools:test_init:test_configure_logging: test_configure_logging\n"
        configure_logging(self.log_file)
        LOGGER.info("test_configure_logging")
        with open(self.log_file, "r") as open_file:
            self.assertEqual(open_file.read(), expected)
