#!/usr/bin/env python3

# From: https://www.stavros.io/posts/python-fuse-filesystem/
#       https://github.com/skorokithakis/python-fuse-sample
import logging
import os
import sys
import errno
from typing import Final

# print(sys.path)

from fuse import FUSE, FuseOSError, Operations
from color_logger import ColourFormatter
from passthrough_ro import PassthroughRO, main
from caching_docker_context import CachingDockerContext

# For error numbers, see https://android.googlesource.com/kernel/lk/+/dima/for-travis/include/errno.h
# ENOTSUP - not suppoerted
# EROFS - Read only file system
# EACCES - Permission denied
# EIO - io error

ROOT_LOGGER : Final = logging.getLogger()
ColourFormatter.add_handler_to(logging.getLogger())
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


class DockerFS(PassthroughRO):
    """This is s FUSE file-system driver for docker assets.
    
    As a file system, we have:
    *--+-- context
       +-- containers
           +-- by-uuid
           +-- by-name
           +-- running
               +-- by-uuid
               +-- by-name
               
       +-- images
           +-- by-uuid
           +-- by-name
       +-- volumes
           +-- by-uuid
           +-- by-name
    
    """
    
    

    def __init__(self, root):
        super().__init__(root)
        self.docker = CachingDockerContext()


    # Filesystem methods
    # ==================

    def access(self, path: str, mode: int):
        if mode in (os.R_OK, os.F_OK):
            logger.debug(f"access(self, {path=}, {mode=})")
            return 0
        logger.warning(f"access(self, {path=}, {mode=})")
        raise FuseOSError(errno.EACCES)

    def getattr(self, path: str, fh=None):
        logger.debug(f"getattr(self, {path=}, {fh=})")
        if path == "/":
            return self.docker.getattr_()
        parts = path.split('/')
        if len(parts) == 2:
            parts.append(None)
        assert len(parts) == 3, "Only expect docker object type and (optionally) name"
        assert parts[0] == "", "Path needs to start with `/`."
        method = getattr(CachingDockerContext, f"getattr_{parts[1]}")
        if not method:
            logger.warning(f"getattr(self, {path=}, {fh=}): Path is not registered.")
            raise FuseOSError(errno.ENOENT)

        result = method(self.docker, parts[2])
        return result


    def readdir(self, path: str, fh):
        logger.debug(f"readdir(self, {path=}, {fh=})")
        assert path[0] == '/'
        path = path[1:]
        reader = getattr(CachingDockerContext, f"list_{path}")
        if not reader:
          logger.warning(f"readdir(self, {path=}, {fh=}): Path is not registered.")
          raise FuseOSError(errno.ENOENT)

        yield "."
        yield ".."
        yield from reader(self.docker)

    def readlink(self, path):
        logger.debug(f"readlink(self, {path=})")
        pathname = os.readlink(self._full_path(path))
        if pathname.startswith("/"):
            # Path name is absolute, sanitize it.
            return os.path.relpath(pathname, self.root)
        else:
            return pathname


    # File methods
    # ============

    def open(self, path: str, flags):
        logger.debug(f"open(self, {path=}, {flags=})")
        full_path = self._full_path(path)
        return os.open(full_path, flags)

    def read(self, path: str, length: int, offset, fh):
        logger.debug(f"read(self, {path=}, {length=}, {offset=}, {fh=})")
        os.lseek(fh, offset, os.SEEK_SET)
        return os.read(fh, length)

    def release(self, path: str, fh):
        logger.debug(f"release(self, {path=}, {fh=})")
        return os.close(fh)


if __name__ == '__main__':
    main(sys.argv[2], sys.argv[1], DockerFS)

