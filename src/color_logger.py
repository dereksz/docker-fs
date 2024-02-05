import logging

class ColourFormatter(logging.Formatter):

    red = "\x1b[31;20m"
    bold_red = "\x1b[31;1m"
    green = "\x1b[32;20m"
    yellow = "\x1b[33;20m"
    blue = "\x1b[34;20m"
    magenta = "\x1b[35;20m"
    cyan = "\x1b[36;20m"
    grey = "\x1b[37;20m"
    reset = "\x1b[0m"
    format_template = '%(levelname)s - %(name)s - %(funcName)s - %(message)s - (%(pathname)s:%(lineno)d)'

    FORMATS: tuple[tuple[int, str], ...] = (
        (logging.DEBUG, grey + format_template + reset),
        (logging.INFO, cyan + format_template + reset),
        (logging.WARNING, yellow + format_template + reset),
        (logging.ERROR, red + format_template + reset),
        (logging.CRITICAL, bold_red + format_template + reset),
    )

    def __init__(self, *args, **kwargs):
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

      
    @classmethod
    def add_handler_to(cls, logger: logging.Logger, stream=None, level=logging.DEBUG) -> logging.Logger:
        h = logging.StreamHandler(stream)
        h.setLevel(level)
        h.setFormatter(ColourFormatter())
        logger.addHandler(h)
        return logger


def getColourStreamHandler(stream=None, level=logging.DEBUG) -> logging.StreamHandler:
    h = logging.StreamHandler(stream)
    h.setLevel(level)
    h.setFormatter(ColourFormatter())
    return h


def getColorLogger(name: str) -> logging.Logger:
    l = logging.getLogger(name)
    ColourFormatter.add_handler_to(l)
    return l