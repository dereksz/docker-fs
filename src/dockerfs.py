#!/usr/bin/env python3

# From: https://www.stavros.io/posts/python-fuse-filesystem/
#       https://github.com/skorokithakis/python-fuse-sample
import logging
import os
import sys
import errno
from typing import Final, List, NoReturn, Optional
from color_logger import ColourFormatter, getColourStreamHandler


# print(sys.path)

from fuse import FUSE, FuseOSError, Operations
from passthrough_ro import PassthroughRO, main
from caching_docker_context import CachingDockerContext

# For error numbers, see https://android.googlesource.com/kernel/lk/+/dima/for-travis/include/errno.h
# ENOTSUP - not suppoerted
# EROFS - Read only file system
# EACCES - Permission denied
# EIO - io error

ROOT_LOGGER : Final = logging.getLogger()
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
        parts : List[Optional[str]] = path.split('/')
        if len(parts) == 2:
            parts.append(None)
        assert len(parts) == 3, "Only expect docker object type and (optionally) name"
        assert parts[0] == "", "Path needs to start with `/`."
        method = getattr(CachingDockerContext, f"getattr_{parts[1]}")
        if not method:
            logger.warning(f"getattr(self, {path=}, {fh=}): Path is not registered.")
            raise FuseOSError(errno.ENOENT)

        result = method(self.docker, parts[2])
        assert isinstance(result, dict), "getattr must return a dict"
        return result


    def readdir(self, path: str, fh):
        logger.debug(f"readdir(self, {path=}, {fh=})")
        assert path[0] == '/'
        path = path[1:]
        reader = getattr(CachingDockerContext, f"readdir_{path}")
        if not reader:
          logger.warning(f"readdir(self, {path=}, {fh=}): Path is not registered.")
          raise FuseOSError(errno.ENOENT)

        yield "."
        yield ".."
        yield from reader(self.docker)


    def readlink(self, path):
        logger.debug(f"readlink(self, {path=})")
        return self.docker.readlink(path)


    # File methods
    # ============

    def open(self, path: str, flags: int):
        logger.debug(f"open(self, {path=}, {flags=})")
        fd = self.docker.open(path, flags)
        logger.debug(f"open(self, {path=}, {flags=}) -> {fd}")
        return fd


    def read(self, path: str, length: int, offset, fh):
        logger.debug(f"read(self, {path=}, {length=}, {offset=}, {fh=})")
        return self.docker.read(path, length, offset, fh)


    def flush(self, path: str, fh) -> None:
        logger.warning(f"flush(self, {path=}, {fh=}) - RO file-system, not expecting to flush")


    def release(self, path: str, fh):
        logger.debug(f"release(self, {path=}, {fh=})")
        return self.docker.release(path, fh)


if __name__ == '__main__':
    COLOUR_HANDLER : Final = getColourStreamHandler()
    ROOT_LOGGER.addHandler(COLOUR_HANDLER)
    for h in ROOT_LOGGER.handlers:
        if h is not COLOUR_HANDLER:
            ROOT_LOGGER.removeHandler(h)
    ROOT_LOGGER.setLevel(logging.DEBUG)
    
    main(sys.argv[2], sys.argv[1], DockerFS)

