"""Defines DockerOperations class for FUSE with the required call-backs."""
import logging
import os
import errno
from typing import List, Optional


from fuse import FuseOSError, Operations
from docker_context import DockerContext, DockerContextWithRead

# Errors we're most likely to return.
# ENOTSUP - not suppoerted
# EROFS - Read only file system
# EACCES - Permission denied
# EIO - io error

logger = logging.getLogger(__name__)


class DockerOperations(Operations):
    """This is s FUSE file-system driver for docker assets.

    Based loosely on:
        - https://www.stavros.io/posts/python-fuse-filesystem/
        - https://github.com/skorokithakis/python-fuse-sample

    """

    docker: DockerContext

    def __init__(self, docker_socket: Optional[str] = None):
        super().__init__()
        self.docker = DockerContext(docker_socket)


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


    # pylint: disable=logging-fstring-interpolation

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
            result["st_nlink"] = len(DockerContext.ROOT_FOLDERS)
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

            method = getattr(DockerContext, f"getattr_{parts[1]}")
            if not method:
                logger.warning(f"getattr(self, {path=}, {fh=}): Path is not registered.")
                raise FuseOSError(errno.ENOENT)

            result = method(self.docker, parts[2])

        assert isinstance(result, dict), "getattr must return a dict"
        logger.info(f"getattr(self, {path=}, {fh=}) ->\n%s\n", result)
        return result


    def readdir(self, path: str, fh):
        # logger.debug(f"readdir(self, {path=}, {fh=})")
        assert path[0] == '/'
        path = path[1:]
        reader = getattr(DockerContext, f"readdir_{path}")
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


class DockerOperationsWithRead(DockerOperations):
    """TODO: Allows the files to be read for extra info."""

    docker: DockerContextWithRead

    # File methods
    # ============

    # pylint: disable=logging-fstring-interpolation
    # pylint: disable=no-member

    def open(self, path: str, flags: int):
        logger.debug(f"open(self, {path=}, {flags=})")
        fd = self.docker.open(path, flags)
        logger.debug(f"open(self, {path=}, {flags=}) -> {fd}")
        return fd


    def read(self, path: str, size: int, offset, fh):
        logger.debug(f"read(self, {path=}, {size=}, {offset=}, {fh=})")
        return self.docker.read(path, size, offset, fh)


    def flush(self, path: str, fh) -> None:
        logger.warning(f"flush(self, {path=}, {fh=}) - RO file-system, not expecting to flush")


    def release(self, path: str, fh):
        logger.debug(f"release(self, {path=}, {fh=})")
        return self.docker.release(path, fh)
