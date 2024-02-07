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
from caching_docker_context import CachingDockerContext, file_attr_to_str

# For error numbers, see https://android.googlesource.com/kernel/lk/+/dima/for-travis/include/errno.h
# ENOTSUP - not suppoerted
# EROFS - Read only file system
# EACCES - Permission denied
# EIO - io error

ROOT_LOGGER : Final = logging.getLogger()
logger = logging.getLogger(__name__)


class DockerFS(Operations):
    """This is s FUSE file-system driver for docker assets."""

    def __init__(self, root, socket: Optional[str] = None):
        super().__init__()
        self.docker = CachingDockerContext(socket)


    def __call__(self, op, *args):
        logger.debug("FUSE op being called: %s%s", op, (*args,))
        if not hasattr(self, op):
            raise FuseOSError(errno.EFAULT)
        try:
            result = getattr(self, op)(*args)
            logging.info("FUSE op returned: %s() -> %s", op, result)
            return result
        except Exception as e:
            logger.exception("Exception calling %s: %s", op, e, exc_info=False, stack_info=False)
            raise


    # Filesystem methods
    # ==================

    def access(self, path: str, amode: int):
        if amode in (os.R_OK, os.F_OK):
            logger.info(f"access(self, {path=}, {amode=}) -> granted")
            return 0
        logger.warning(f"access(self, {path=}, {amode=}): amode not permitted")
        raise FuseOSError(errno.EACCES)

    def getattr(self, path: str, fh=None):
        logger.debug(f"getattr(self, {path=}, {fh=})")
        if path == "/":
            result = self.docker.getattr_()
            result["st_nlink"] = len(CachingDockerContext.ROOT_FOLDERS)
        else:
            parts : List[Optional[str]] = path.split('/')
            if len(parts) == 2:
                parts.append(None)
            if (
                len(parts) != 3
                or parts[0] != ""
                or parts[1] not in (
                    "volumes",
                    "images",
                    "containers"
                )
            ):
                logger.warning(f"getattr(self, {path=}, {fh=}): Path is not registered.")
                raise FuseOSError(errno.ENOENT)

            method = getattr(CachingDockerContext, f"getattr_{parts[1]}")
            if not method:
                logger.warning(f"getattr(self, {path=}, {fh=}): Path is not registered.")
                raise FuseOSError(errno.ENOENT)

            result = method(self.docker, parts[2])

        assert isinstance(result, dict), "getattr must return a dict"
        logger.info(f"getattr(self, {path=}, {fh=}) ->\n%s\n", file_attr_to_str(result))
        return result


    def readdir(self, path: str, fh):
        # logger.debug(f"readdir(self, {path=}, {fh=})")
        assert path[0] == '/'
        path = path[1:]
        reader = getattr(CachingDockerContext, f"readdir_{path}")
        if not reader:
            logger.warning(f"readdir(self, {path=}, {fh=}): Path is not registered.")
            raise FuseOSError(errno.ENOENT)

        yield "."
        yield ".."
        files = list(reader(self.docker))
        logger.info(f"readdir(self, {path=}, {fh=}) found %i files", len(files))
        yield from files


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
    COLOUR_HANDLER.setLevel(logging.DEBUG)
    ROOT_LOGGER.addHandler(COLOUR_HANDLER)
    for h in ROOT_LOGGER.handlers:
        if h is not COLOUR_HANDLER:
            ROOT_LOGGER.removeHandler(h)

    ROOT_LOGGER.setLevel(logging.INFO)
    logger.setLevel(logging.DEBUG)

    fuse_log = logging.getLogger("fuse")
    fuse_log.addHandler(COLOUR_HANDLER)
    fuse_log.setLevel(logging.INFO)

    main(sys.argv[2], sys.argv[1], DockerFS, sys.argv[3] if len(sys.argv) > 3 else None, debug=False)
