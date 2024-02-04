"""File constants for `stat`, named after the C macros of the same (similar) name."""

from typing import Final


S_IFIFO  : Final = 0o00010000   # pipe
S_IFCHR  : Final = 0o00020000   # character device
S_IFDIR  : Final = 0o00040000   # directory
S_IFBLK  : Final = 0o00060000   # block device
S_IFREG  : Final = 0o00100000   # regular

S_IFLNK  : Final = 0o00120000   # sym-link
S_IFSOCK : Final = 0o00140000   # Socket    

S_IFMT   : Final = 0o00170000   # file type mask

S_IRALL  : Final = 0o00000222   # Readable by all
S_IXALL  : Final = 0o00000111   # Executable by all (means "listable" for a directory!)
