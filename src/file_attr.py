"""Defines helper class ``FileAttr`` to use instead of a regular
``dict`` when dealing with ``stat`` structures.
"""
from datetime import datetime
from typing import Callable, Dict, Final, Generator, List, SupportsIndex, Tuple, Union


# Extra file mode bit masks
S_IRALL : Final = 0o00000444   # Readable by all
S_IXALL : Final = 0o00000111   # Executable by all (means "listable" for a directory!)


class FileAttr(Dict[str, int | float]):
    """Adds custom __str__ to format time stamps and octal fields in a `stat` structure.."""

    def items_formatted(self) -> Generator[Tuple[str, str], None, None]:
        """Returns key/value pirs, but with the value formatted for human
        (programmer) consumption.
        """
        for key, value in self.items():
            formatter = _FORMATTERS.get(key, str)
            str_value = formatter(value) # type: ignore[arg-type]
            yield (key, str_value)


    def __str__(self) -> str:
        """`str()` function for `FileAttra`s.

        Returns:
            A YAML-like sting using "key: value", one line per key.
            If you want more control over formatting, call
            ``items_formatted()`` and iterate directly.
        """
        lines: List[str] = []
        for key, value in self.items_formatted():
            lines.append(f"{key}: {value}")
        return "\n".join(lines)
    
    __repr__ = __str__
    
    def copy(self) -> "FileAttr":
        return FileAttr(self.items())
        

# Static helpers

_TIME_FMT = Callable[[float], str]
_OCTAL_FMT = Callable[[int], str]
_FMT_T = Union[_TIME_FMT, _OCTAL_FMT]

def __format_time(timet: float) -> str:
    return datetime.fromtimestamp(timet).isoformat()

def __format_octal(value: int) -> str:
    return oct(value)

_FORMATTERS: Final[Dict[str, _FMT_T]] = {
    "st_ctime": __format_time,
    "st_mtime": __format_time,
    "st_atime": __format_time,
    "st_birthtime": __format_time,
    "st_mode": __format_octal,
}
