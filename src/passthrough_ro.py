#!/usr/bin/env python3

"""Passthrough file system that "bind-mounts" another system.

From: 
  - https://www.stavros.io/posts/python-fuse-filesystem/
  - https://github.com/skorokithakis/python-fuse-sample
"""

import os
import sys
import errno
import logging
from typing import Any, Generator


from fuse import FUSE, FuseOSError

from passthrough import Passthrough, main
# For error numbers, see https://android.googlesource.com/kernel/lk/+/dima/for-travis/include/errno.h
# ENOTSUP - not suppoerted
# EROFS - Read only file system
# EACCES - Permission denied
# EIO - io error


logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)



class PassthroughRO(Passthrough):

    # Filesystem methods
    # ==================

    def access(self, path: str, mode: int):
        if mode & os.O_WRONLY:
            logger.error(f"access(self, {path=}, {mode=}) - requesting write access on RO file-system")
            raise FuseOSError(errno.EROFS)
        return super().access(path, mode)

    def chmod(self, path: str, mode: int):
        logger.error(f"chmod(self, {path=}, {mode=}) - requesting changes on RO file-system")
        raise FuseOSError(errno.EROFS)

    def chown(self, path: str, uid, gid):
        logger.error(f"chown(self, {path=}, {uid=}, {gid=}) - requesting changes on RO file-system")
        raise FuseOSError(errno.EROFS)

    def getattr(self, path: str, fh=None):
        logger.debug(f"getattr(self, {path=}, {fh=})")
        full_path = self._full_path(path)
        st = os.lstat(full_path)
        return dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime',
                     'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))

    def readdir(self, path: str, fh) -> Generator[str, Any, None]:
        logger.debug(f"readdir(self, {path=}, {fh=})")
        full_path = self._full_path(path)
        dirents = ['.', '..']
        if os.path.isdir(full_path):
            dirents.extend(os.listdir(full_path))
        yield from dirents

    def readlink(self, path):
        logger.warning(f"readlink(self, {path=}) - Not Supported - ENOTSUP")
        raise FuseOSError(errno.ENOTSUP)

    def mknod(self, path: str, mode, dev):
        logger.error(f"mknod(self, {path=}, {mode=}, {dev=}) - requesting changes on RO file-system")
        raise FuseOSError(errno.EROFS)

    def rmdir(self, path):
        logger.error(f"rmdir(self, {path=}) - requesting changes on RO file-system")
        raise FuseOSError(errno.EROFS)

    def mkdir(self, path: str, mode: int):
        logger.error(f"mkdir(self, {path=}, {mode=}) - requesting changes on RO file-system")
        raise FuseOSError(errno.EROFS)

    def statfs(self, path):
        logger.warning(f"statfs(self, {path=}) - Not Supported - ENOTSUP")
        raise FuseOSError(errno.ENOTSUP)

    def unlink(self, path):
        logger.error(f"unlink(self, {path=}) - requesting changes on RO file-system")
        raise FuseOSError(errno.EROFS)

    def symlink(self, name, target):
        logger.error(f"symlink(self, {name=}, {target=}) - requesting changes on RO file-system")
        raise FuseOSError(errno.EROFS)

    def rename(self, old, new):
        logger.error(f"rename(self, {old=}, {new=}) - requesting changes on RO file-system")
        raise FuseOSError(errno.EROFS)

    def link(self, target, name):
        logger.error(f"link(self, {target=}, {name=}) - requesting changes on RO file-system")
        raise FuseOSError(errno.EROFS)

    def utimens(self, path: str, times=None):
        logger.error(f"utimens(self, {path=}, {times=}) - requesting changes on RO file-system")
        raise FuseOSError(errno.EROFS)


    # File methods
    # ============

    def open(self, path: str, flags):
        logger.debug(f"open(self, {path=}, {flags=})")
        full_path = self._full_path(path)
        return os.open(full_path, flags)

    def create(self, path: str, mode, fi=None):
        logger.error(f"create(self, {path=}, {mode=}, {fi=}) - requesting changes on RO file-system")
        raise FuseOSError(errno.EROFS)

    def read(self, path: str, length: int, offset, fh):
        logger.debug(f"read(self, {path=}, {length=}, {offset=}, {fh=})")
        os.lseek(fh, offset, os.SEEK_SET)
        return os.read(fh, length)

    def write(self, path: str, buf, offset, fh):
        logger.error(f"write(self, {path=}, buf, {offset=}, {fh=}) - requesting changes on RO file-system")
        raise FuseOSError(errno.EROFS)

    def truncate(self, path: str, length: int, fh=None):
        logger.error(f"truncate(self, {path=}, {length=}, {fh=}) - requesting changes on RO file-system")
        raise FuseOSError(errno.EROFS)

    def flush(self, path: str, fh):
        logger.error(f"flush(self, {path=}, {fh=}) - requesting changes on RO file-system")
        raise FuseOSError(errno.EROFS)

    def release(self, path: str, fh):
        logger.debug(f"release(self, {path=}, {fh=})")
        return os.close(fh)

    def fsync(self, path: str, fdatasync, fh):
        logger.warning(f"fsync(self, {path=}, {fdatasync=}, {fh=}) - RO filesystem - NoOp")


if __name__ == '__main__':
    main(sys.argv[2], sys.argv[1], cls=PassthroughRO)