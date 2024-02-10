"""Classes, methods, functions, and constants to help re-present docker assets as
file-system entities.  (Files, Folders, Sym-links, with appropriate attributes.)
"""
import sys
from typing import Dict, Final, Generator, Iterable, List, Optional
from datetime import datetime
import errno
import logging

from stat import S_IFDIR, S_IFREG, S_IFLNK, S_IMODE

import docker
from docker.models.resource import (
    Collection as DockerCollection,
    Model as _DockerModel
)
from fuse import FuseOSError

from file_attr import S_IRALL, S_IXALL, FileAttr


LOGGER: Final = logging.getLogger(__name__)

class DockerModel(_DockerModel):
    """DockerModel will be a Docker Volume, Image or Container.

    We use our own "base" class, as the Docker base class didn't include
    ``tags``, even though all of the derived classes (at least, that we're
    interested in) include this field.
    """

    tags: Iterable[str]


class DockerContext():
    """Main Context for helping us query Docker assets in a file-like manner."""

    client: docker.client.DockerClient
    volume_symlinks: Dict[str, str]
    image_symlinks: Dict[str, str]
    container_symlinks: Dict[str, str]

    # Linux: 'unix:///var/run/docker.sock'
    # Mac colima: "unix:~/.colima/default/docker.sock"
    def __init__(self, base_url: str | None = None):
        if base_url is None:
            context_api = docker.ContextAPI()
            context = context_api.get_current_context()
            base_url = context.Host
        self.client = docker.client.DockerClient(base_url=base_url)
        self.volume_symlinks = {}
        self.image_symlinks = {}
        self.container_symlinks = {}


    ROOT_FOLDERS: Final = (
      ".",
      "..",
      "volumes",
      "images",
      "containers",
    )
    """These are the folders that are exposed at the root of the filesystem."""


    # sym-link calls

    def readlink(self, name: str) -> str:
        """Dereference a sym-link into a file name / path."""
        parts = name.split('/')
        try:
            assert len(parts) == 3
            assert parts[0] == ''
            symlinks = {
                "volumes": self.volume_symlinks,
                "images": self.image_symlinks,
                "containers": self.container_symlinks,
            }[parts[1]]
            dest_name = symlinks[parts[2]]
            return dest_name
        except Exception as e:
            raise FuseOSError(errno.ENOENT) from e


    # `readdir` calls

    def readdir_(self) -> Generator[str,None,None]:
        """Generate folder names for filesystem root."""
        yield from self.__class__.ROOT_FOLDERS

    def readdir_volumes(self) -> Generator[str,None,None]:
        """Generate volume names and sha256's."""
        syms : Dict[str, str] = {}
        self.volume_symlinks = syms
        for i in self.client.volumes.list():
            name = i.name
            yield name
            sha256 = i.id
            if sha256.startswith("sha256:"):
                sha256 = sha256[7:]
            if sha256 != name:
                sha256 = '.' + sha256
                yield sha256
                syms[name] = sha256

    def readdir_images(self) -> Generator[str,None,None]:
        """Generate image names and sha256's."""
        syms : Dict[str, str] = {}
        self.image_symlinks = syms
        for i in self.client.images.list(all=True):
            sha256 = i.id
            assert sha256.startswith("sha256:")
            sha256 = '.' + sha256[7:]
            syms.update({ t: sha256 for t in i.tags })
            yield from i.tags
            yield sha256

    def readdir_containers(self) -> Generator[str,None,None]:
        """Generate container names and sha256's."""
        syms : Dict[str, str] = {}
        self.container_symlinks = syms
        for i in self.client.containers.list(all=True):
            name = i.name
            sha256 = '.' + i.id
            syms[name] = sha256
            yield name
            yield sha256


    # `getattr` calls

    def getattr_( # pylint: disable=too-many-arguments
        self,
        is_file: bool = False,
        mode: Optional[int] = None,
        atime: Optional[float] = None,
        ctime: Optional[float] = None,
        mtime: Optional[float] = None,
        size: int = 1000,
    ) -> FileAttr:
        """Called for the root of the file system,
        and as a base for when getting file and directory attras.
        """
        now_ish = float(1707020058.716742869)
        attr : FileAttr = {
          'st_atime': atime or now_ish,
          'st_ctime': ctime or now_ish,
          'st_uid': 0, # 0 == root
          'st_gid': 0, # 0 == root / wheel
          'st_mode': mode if mode else S_IRALL | (S_IFREG if is_file else S_IFDIR | S_IXALL),
          'st_mtime': mtime or now_ish,
          'st_nlink': 1 if is_file else 2,
        }
        # if size:
        attr['st_size'] = size or 1000
        return attr


    def _find_from_name(self, collection: DockerCollection, name: str) -> DockerModel:
        model: DockerModel
        if name[0] == '.':
            name = name[1:] # "sha256:" +
        try:
            model = collection.get(name)
        except docker.errors.NotFound as e:
            LOGGER.warning("Can't find '%s'.", name)
            raise FuseOSError(errno.ENOENT) from e
        return model


    def _find_from_path(self, path: str) -> DockerModel:
        parts = path.split('/')

        assert len(parts) == 3
        assert parts[0] == ''

        collection: DockerCollection

        if parts[1] == "volumes":
            collection = self.client.volumes
        elif parts[1] == "images":
            collection = self.client.images
        elif parts[1] == "containers":
            collection = self.client.containers
        else:
            raise FuseOSError(errno.ENOENT)

        return self._find_from_name(collection=collection, name=parts[2])


    def _getattr_from_model(self, collection: DockerCollection, name: str) -> FileAttr:
        model = self._find_from_name(collection, name)
        attr = self.getattr_(is_file=True).copy()
        attrs = model.attrs
        created : str = attrs.get("Created") or attrs.get("CreatedAt") # the latter for volumes
        ctime = datetime.fromisoformat(created).timestamp()
        size = attrs.get("Size",1000)
        attr["st_ctime"] = ctime
        attr["st_mtime"] = ctime
        attr["st_atime"] = ctime
        attr["st_size"] = size
        if name and name[0] != '.': # probably a sym-link
            if (
                name in self.volume_symlinks
                or name in self.image_symlinks
                or name in self.container_symlinks
            ):
                mode: int = int(attr["st_mode"])
                mode = S_IMODE(mode) | S_IFLNK
                attr["st_mode"] = mode
        return attr


    def _getattr_from_collection(self, collection: DockerCollection, **list_kwargs) -> FileAttr:
        attr = self.getattr_(is_file=False).copy()
        ctime = attr["st_ctime"]
        size = 0
        count = 0
        for model in collection.list(**list_kwargs):
            attrs = model.attrs
            created : str = attrs.get("Created") or attrs.get("CreatedAt")
            this_ctime = datetime.fromisoformat(created).timestamp()
            if this_ctime > ctime:
                ctime = this_ctime
            size += attrs.get("Size", 0)
            count += 1
        attr["st_ctime"] = ctime
        attr["st_mtime"] = ctime
        attr["st_atime"] = ctime
        attr["st_size"] = size or 1000 # Fake for fuse. Zero can be problematic.
        if sys.platform == "darwin":
            attr["st_birthtime"] = ctime
            attr["st_nlink"] += count # MacOS includes files in the nlink numbert too
        return attr


    def _getattr(
            self,
            collection: DockerCollection,
            name: Optional[str],
            **list_kwargs
    ) -> FileAttr:
        attr = (
            self._getattr_from_model(collection, name)
            if name else
            self._getattr_from_collection(collection, **list_kwargs)
        )
        return attr


    def getattr_volumes(self, name: Optional[str]) -> FileAttr:
        """Get attributes for a volume (if ``name`` not None)
        or for the "volumes" folder (if ``name`` is None).
        """
        return self._getattr(self.client.volumes, name)

    def getattr_images(self, name: Optional[str]) -> FileAttr:
        """Get attributes for a image (if ``name`` not None)
        or for the "imagess" folder (if ``name`` is None).
        """
        return self._getattr(self.client.images, name, all=True)

    def getattr_containers(self, name: Optional[str]) -> FileAttr:
        """Get attributes for a container (if ``name`` not None)
        or for the "containers" folder (if ``name`` is None).
        """
        return self._getattr(self.client.containers, name, all=True)



class DockerContextWithRead(DockerContext):
    """TODO: Add the reading of the docker models as files."""
    # pylint: disable=logging-fstring-interpolation

    file_desciptors: List[Optional[DockerModel]]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.file_desciptors = [None] * 100


    def open(self, path: str, flags: int) -> int:
        """Open Docker Model for reading."""
        LOGGER.info(f"open(self, {path=}, {flags=})")
        model = self._find_from_path(path)
        idx = self.file_desciptors.index(None, 3)
        self.file_desciptors[idx] = model
        return idx

    def read(self, path: str, length: int, offset, fh) -> bytes:
        """Read data from Docker Model."""
        LOGGER.info(f"read(self, {path=}, {length=}, {offset=}, {fh=})")
        # The reality is that we need the size in mt_size to be "accurate" for
        # actual file reading (e.g. `cat` to work correctly.)
        return "Hello from Docker\n".encode("utf-8")

    def release(self, path: str, fh) -> int:
        """Open Docker Model file handle.  (I.e. "close".)"""
        LOGGER.info(f"release(self, {path=}, {fh=})")
        assert self.file_desciptors[fh] is not None
        self.file_desciptors[fh] = None
        return 0
