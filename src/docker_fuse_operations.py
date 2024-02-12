"""Defines DockerOperations class for FUSE with the required call-backs."""
import logging
import os
from errno import EACCES, EFAULT, ENOTSUP, ENOENT
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
        method = getattr(self, op)
        if method is None:
            logger.warning("FUSE call-back not defined: %s", op)
            raise FuseOSError(EFAULT)
        try:
            result = method(*args)
            logging.info("FUSE op returned: %s() -> %s", op, result)
            return result
        except Exception as e:
            if isinstance(e, FuseOSError):
                if e.errno not in (ENOTSUP, ENOENT):
                    logger.warning("Exception calling %s: %s", op, e, exc_info=False, stack_info=False)
            else:
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
        raise FuseOSError(EACCES)


    def getxattr(self, path, name, position=0):
        logger.debug(f"getxattr(self, {path=}, {name=}, {position=})")
        return b''
        raise FuseOSError(ENOTSUP)

    def getattr(self, path: str, fh=None):
        logger.debug(f"getattr(self, {path=}, {fh=})")
        if path == "/":
            result = self.docker.getattr_()
            result["st_nlink"] = len(DockerContext.ROOT_FOLDERS)
        else:
            parts: List[str|None] = path.split('/', maxsplit=2)  # type: ignore[assignment]
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
                if not path.startswith("/.Trash"):
                    logger.warning(f"getattr(self, {path=}, {fh=}): Path is not registered.")
                raise FuseOSError(ENOENT)

            method = getattr(DockerContext, f"getattr_{parts[1]}")
            if not method:
                logger.warning(f"getattr(self, {path=}, {fh=}): Path is not registered.")
                raise FuseOSError(ENOENT)

            result = method(self.docker, parts[2])

        assert isinstance(result, dict), "getattr must return a dict"
        logger.info(f"getattr(self, {path=}, {fh=}) ->\n%s\n", result)
        return result


    def readdir(self, path: str, fh):
        logger.debug(f"readdir(self, {path=}, {fh=})")
        assert path[0] == '/'
        rel_path = path[1:]
        tag_prefix: str | None = None
        if '/' in rel_path:
            rel_path, tag_prefix = rel_path.split("/", maxsplit=1)
        reader = getattr(DockerContext, f"readdir_{rel_path}")
        if not reader:
            logger.warning(f"readdir(self, {path=}, {fh=}): Path is not registered.")
            raise FuseOSError(ENOENT)

        yield "."
        yield ".."
        try:
            file_generator = reader(self.docker, tag_prefix)
        except TypeError as e:
            logger.error('tag_prefix was not expected on "readdir_%s"', rel_path)
            raise
        files = list(file_generator)
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
