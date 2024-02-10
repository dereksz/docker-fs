#!/usr/bin/env python3
"""Entry script for DockerFS."""

import os
from stat import S_IFMT, S_IFDIR, S_IFIFO, S_IFSOCK
import sys
import logging
import argparse
from typing import Final

from fuse import FUSE

from color_logger import make_color_stream_handler
from docker_fuse_operations import DockerOperations

ROOT_LOGGER: Final = logging.getLogger()
FUSE_LOGGER: Final = logging.getLogger("fuse")
LOGGER: Final = logging.getLogger(__name__)


def check_socket_or_port(arg: str) -> str:
    """Checks the arg is a unix socker of a TCP/IP port / HTTP address."""
    parts = arg.split("://", maxsplit=2)
    if "http" in parts[0].lower():
        return arg
    # Deal with when no protocol
    if len(parts) == 1:
        parts = ["unix", arg]
    if parts[0] == "unix":
        try:
            stat = os.stat(parts[1])
        except Exception as e:
            LOGGER.warning("`stat` failed -> %s", e)
        else:
            mode = stat.st_mode
            LOGGER.debug("check_socket_or_port: %s mode: %#08o", arg, mode)
            if S_IFMT(mode) in (S_IFIFO, S_IFSOCK):
                return "unix://" + parts[1]

    raise argparse.ArgumentTypeError(f"Source does not exist or is not supported: {arg}")


def check_folder(arg: str) -> str:
    """Checks the arg is an existing folder."""
    try:
        stat = os.stat(arg)
    except Exception as e:
        LOGGER.warning("`stat` failed -> %s", e)
    else:
        mode = stat.st_mode
        LOGGER.debug("check_folder: %s mode: %#08o", arg, mode)
        if S_IFMT(mode) in (S_IFDIR,):
            return arg

    raise argparse.ArgumentTypeError(f"Source does not exist or is not supported: {arg}")


def make_parser():
    """Makes Parser resdy to parses args passed to script."""

    parser = argparse.ArgumentParser(
        prog='DockerFS',
        description='Creates virtual file system exposing Docker asset names and dates.',
    )
    parser.add_argument(
        "mount_point", nargs="?", type=check_folder, default=".dockerfs",
        help="Mount point for docker virtual file system.  Defaults to `.dockerfs`."
    )
    parser.add_argument(
        "docker_source", nargs="?", type=check_socket_or_port,
        help="Socket or port to connect to docker, e.g. `unix:///var/run/docker.sock`.  "
             "Will ask and use dockers 'Host' from the default context is not supplied."
    )
    parser.add_argument("--verbose", "-v", action='store_true', help="Enables DEBUG level tracing")
    parser.add_argument("--quiet", "-q", action='store_true', help="Drops to WARNING level tracing")
    parser.add_argument("--debug-fuse", action='store_true',
                        help="Enables debugging in fusepy library.")

    return parser


def setup_loggers(): # pylint: disable=unused-argument
    """Setup loggers."""
    for h in ROOT_LOGGER.handlers:
        ROOT_LOGGER.removeHandler(h)
    color_handler: Final = make_color_stream_handler(level=logging.DEBUG)

    ROOT_LOGGER.addHandler(color_handler)
    FUSE_LOGGER.addHandler(color_handler)
    LOGGER.addHandler(color_handler)

    ROOT_LOGGER.setLevel(logging.DEBUG)
    FUSE_LOGGER.setLevel(logging.DEBUG)
    LOGGER.setLevel(logging.DEBUG)


def setup_log_levels(args: argparse.Namespace): # pylint: disable=unused-argument
    """Setup logging levels per arguments."""
    log_level: Final = (
        logging.DEBUG if args.verbose
        else logging.WARNING if args.quiet
        else logging.INFO
    )
    ROOT_LOGGER.setLevel(log_level)
    FUSE_LOGGER.setLevel(log_level)


def main():
    """Main."""
    setup_loggers()
    parser = make_parser()
    args = parser.parse_args()
    setup_log_levels(args)
    try:
        FUSE(
            operations=DockerOperations(args.docker_source),
            mountpoint=args.mount_point,
            nothreads=True,
            foreground=True,
            debug=args.debug_fuse,
        )
    except RuntimeError as e:
        LOGGER.error("FUSE call failed - is it already mounted?  %s", e)
        sys.exit(-1)


if __name__ == '__main__':
    main()
