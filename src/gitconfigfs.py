#!/usr/bin/env python3

import sys
from passthrough import Passthrough, main

from fuse import FUSE, FuseOSError, Operations
# For error numbers, see https://android.googlesource.com/kernel/lk/+/dima/for-travis/include/errno.h
# ENOTSUP - not suppoerted
# EROFS - Read only file system
# EACCES - Permission denied
# EIO - io error


if __name__ == '__main__':
    main(sys.argv[2], sys.argv[1], Passthrough)