import logging

__version__ = "0.23.0"


LOGGER = logging.getLogger(__name__)
LOGGER.addHandler(logging.NullHandler())


def configure_logging(filename, level=logging.INFO, format_string=None):
    "configure logging to file"
    if not format_string:
        format_string = "%(levelname)s %(name)s:%(module)s:%(funcName)s: %(message)s"
    handler = logging.FileHandler(filename)
    formatter = logging.Formatter(format_string)
    handler.setFormatter(formatter)
    LOGGER.addHandler(handler)
    LOGGER.setLevel(level)
    return handler
