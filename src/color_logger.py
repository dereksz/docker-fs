"""Defines a ColourFormatter for loging to stdout/stderr."""
import logging
import sys

class ColourFormatter(logging.Formatter):
    """Defines a ColourFormatter for loging to stdout/stderr."""

    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    green = "\x1b[32;20m"
    yellow = "\x1b[33;20m"
    blue = "\x1b[34;20m"
    magenta = "\x1b[35;20m"
    cyan = "\x1b[36;20m"
    grey = "\x1b[37;20m"
    reset = "\x1b[0m"
    format_template = \
        '%(levelname)s - %(name)s - %(funcName)s - %(message)s - (%(pathname)s:%(lineno)d)'

    FORMATS: tuple[tuple[int, str], ...] = (
        (logging.DEBUG, blue + format_template + reset),
        (logging.INFO, cyan + format_template + reset),
        (logging.WARNING, yellow + format_template + reset),
        (logging.ERROR, red + format_template + reset),
        (logging.CRITICAL, bold_red + format_template + reset),
    )

    def __init__(self, *args, **kwargs):
        super().__init__()
        self._args = args
        self._kwargs = kwargs
        self._formatters: tuple[tuple[int, logging.Formatter], ...] = tuple(
            (k, logging.Formatter(v, *args, **kwargs)) for k, v in ColourFormatter.FORMATS
        )

    def __get_formatter(self, level: int) -> logging.Formatter:
        for lvl, formatter in self._formatters:
            if level <= lvl:
                return formatter
        return self._formatters[-1][1]

    def format(self, record):
        formatter: logging.Formatter = self.__get_formatter(record.levelno)
        result =  formatter.format(record)
        return result


def make_color_stream_handler(stream=sys.stdout, level=logging.DEBUG):
    """Makes a stream handler with color formatter."""
    h = logging.StreamHandler(stream)
    h.setLevel(level)
    h.setFormatter(ColourFormatter())
    return h


def add_colour_logging_to(
        logger: logging.Logger | str | None,
        stream=sys.stdout,
        level=logging.DEBUG,
) -> logging.Logger:
    """Creates stream handler with colour formatted and attaches it to the given logger."""
    if not isinstance(logger, logging.Logger):
        logger = logging.getLogger(logger)
    h = make_color_stream_handler(stream=stream, level=level)
    logger.addHandler(h)
    logger.setLevel(level)
    return logger
