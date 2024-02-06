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
from typing import Optional


from fuse import FUSE, FuseOSError, Operations
# For error numbers, see https://android.googlesource.com/kernel/lk/+/dima/for-travis/include/errno.h
# ENOTSUP - not suppoerted
# EROFS - Read only file system
# EACCES - Permission denied
# EIO - io error


logging.basicConfig()
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class Passthrough(Operations):
    def __init__(self, root):
        self.root = root

    # Helpers
    # =======

    def _full_path(self, partial):
        partial = partial.lstrip("/")
        path = os.path.join(self.root, partial)
        return path

    # Filesystem methods
    # ==================

    def access(self, path: str, amode: int):
        logger.debug(f"access(self, {path=}, {amode=})")
        full_path = self._full_path(path)
        if not os.access(full_path, amode):
            raise FuseOSError(errno.EACCES)

    def chmod(self, path: str, mode: int):
        logger.debug(f"chmod(self, {path=}, {mode=})")
        full_path = self._full_path(path)
        return os.chmod(full_path, mode)

    def chown(self, path: str, uid, gid):
        logger.debug(f"chown(self, {path=}, {uid=}, {gid=})")
        full_path = self._full_path(path)
        return os.chown(full_path, uid, gid)

    def getattr(self, path: str, fh=None):
        logger.debug(f"getattr(self, {path=}, {fh=})")
        full_path = self._full_path(path)
        st = os.lstat(full_path)
        return dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime',
                     'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))

    def readdir(self, path: str, fh):
        logger.debug(f"readdir(self, {path=}, {fh=})")
        full_path = self._full_path(path)

        dirents = ['.', '..']
        if os.path.isdir(full_path):
            dirents.extend(os.listdir(full_path))
        yield from dirents

    def readlink(self, path):
        logger.debug(f"readlink(self, {path=})")
        pathname = os.readlink(self._full_path(path))
        if pathname.startswith("/"):
            # Path name is absolute, sanitize it.
            return os.path.relpath(pathname, self.root)
        else:
            return pathname

    def mknod(self, path: str, mode, dev):
        logger.debug(f"mknod(self, {path=}, {mode=}, {dev=})")
        return os.mknod(self._full_path(path), mode, dev)

    def rmdir(self, path):
        logger.debug(f"rmdir(self, {path=})")
        full_path = self._full_path(path)
        return os.rmdir(full_path)

    def mkdir(self, path: str, mode: int):
        logger.debug(f"mkdir(self, {path=}, {mode=})")
        return os.mkdir(self._full_path(path), mode)

    def statfs(self, path):
        logger.debug(f"statfs(self, {path=})")
        full_path = self._full_path(path)
        stv = os.statvfs(full_path)
        return dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree',
            'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files', 'f_flag',
            'f_frsize', 'f_namemax'))

    def unlink(self, path):
        logger.debug(f"unlink(self, {path=})")
        return os.unlink(self._full_path(path))

    def symlink(self, target, source):
        logger.debug(f"symlink(self, {name=}, {target=})")
        return os.symlink(source, self._full_path(target))

    def rename(self, old, new):
        logger.debug(f"rename(self, {old=}, {new=})")
        return os.rename(self._full_path(old), self._full_path(new))

    def link(self, target, source):
        logger.debug(f"link(self, {target=}, {source=})")
        return os.link(self._full_path(target), self._full_path(source))

    def utimens(self, path: str, times=None):
        logger.debug(f"utimens(self, {path=}, {times=})")
        return os.utime(self._full_path(path), times)

    # File methods
    # ============

    def open(self, path: str, flags):
        logger.debug(f"open(self, {path=}, {flags=})")
        full_path = self._full_path(path)
        return os.open(full_path, flags)

    def create(self, path: str, mode, fi=None):
        logger.debug(f"create(self, {path=}, {mode=}, {fi=})")
        full_path = self._full_path(path)
        return os.open(full_path, os.O_WRONLY | os.O_CREAT, mode)

    def read(self, path: str, size: int, offset, fh):
        logger.debug(f"read(self, {path=}, {size=}, {offset=}, {fh=})")
        os.lseek(fh, offset, os.SEEK_SET)
        return os.read(fh, size)

    def write(self, path: str, buf, offset, fh):
        logger.debug(f"write(self, {path=}, buf, {offset=}, {fh=})")
        os.lseek(fh, offset, os.SEEK_SET)
        return os.write(fh, buf)

    def truncate(self, path: str, length: int, fh=None):
        logger.debug(f"truncate(self, {path=}, {length=}, {fh=})")
        full_path = self._full_path(path)
        with open(full_path, 'r+') as f:
            f.truncate(length)

    def flush(self, path: str, fh):
        logger.debug(f"flush(self, {path=}, {fh=})")
        return os.fsync(fh)

    def release(self, path: str, fh):
        logger.debug(f"release(self, {path=}, {fh=})")
        return os.close(fh)

    def fsync(self, path: str, datasync, fh):
        logger.debug(f"fsync(self, {path=}, {datasync=}, {fh=})")
        return self.flush(path, fh)


def main(mountpoint, root, cls=Passthrough, socket: Optional[str] = None, debug=False):
    try:
        FUSE(cls(root, socket), mountpoint, nothreads=True, foreground=True, debug=debug)
    except RuntimeError as e:
        logger.error("FUSE call failed - is it already mounted?  %s", e)
        sys.exit(-1)

if __name__ == '__main__':
    main(sys.argv[2], sys.argv[1])
