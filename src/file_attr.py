"""Defines helper class ``FileAttr`` to use instead of a regular
``dict`` when dealing with ``stat`` structures.
"""
from datetime import datetime
from typing import Callable, Dict, Final, Generator, List, Tuple


# Extra file mode bit masks
S_IRALL : Final = 0o00000444   # Readable by all
S_IXALL : Final = 0o00000111   # Executable by all (means "listable" for a directory!)


class FileAttr(Dict[str, int | float]):
    """Adds custom __str__ to format time stamps and octal fields in a `stat` structure.."""

    def items_formatted(self) -> Generator[Tuple[str, str], None, None]:
        """Returns key/value pirs, but with the value formatted for human (programmer) consumption."""
        for key, value in self.items():
            formatter = __FORMATTERS.get(key, str)
            str_value = formatter(value)
            yield (key, str_value)


    def __str__(self) -> str:
        """`str()` function for `FileAttra`s.

        Returns:
            A YAML-like sting using "key: value", one line per key.
            If you want more control over formatting, call
            ``items_formatted()`` and iterate directly.
        """
        lines = List[str] = []
        for key, value in self.items_formatted():
            lines.append(f"{key}: {value}")
        return "\n".join(lines)


# Static helpers

__TIME_FMT: Final = Callable[[float], str]
__OCTAL_FMT: Final = Callable[[int], str]
__FMT_T: Final = __TIME_FMT | __OCTAL_FMT

def __format_time(timet: float) -> str:
    return datetime.fromtimestamp(timet).isoformat()

__format_octal = oct

__FORMATTERS: Final[Dict[str, __FMT_T]] = {
    "st_ctime": __format_time,
    "st_mtime": __format_time,
    "st_atime": __format_time,
    "st_birthtime": __format_time,
    "st_mode": __format_octal,
}
