import unittest
from docmaptools import parse


class TestParse(unittest.TestCase):
    def setUp(self):
        pass

    def test_dummy(self):
        self.assertTrue(parse.dummy())
