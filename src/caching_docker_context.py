from datetime import datetime
import errno
import logging
from stat import S_IFCHR, S_IFDIR, S_IFREG, S_IFLNK, S_IMODE
import sys
from typing import Dict, Final, Generator, Iterable, List, Optional

import docker

from docker.models.resource import (
    Collection as DockerCollection,
    Model as _DockerModel
)

from fuse import FuseOSError


# Extra file mode bit masks
S_IRALL : Final = 0o00000444   # Readable by all
S_IXALL : Final = 0o00000111   # Executable by all (means "listable" for a directory!)


logger = logging.getLogger(__name__)

START_TIME = datetime(2000, 1, 1)

FileAttra = Dict[str, int | float]

def file_attr_to_str(attr: FileAttra) -> str:
    attr = attr.copy()
    lines : List[str] = []
    for keys, formatter in (
        (("st_ctime", "st_mtime", "st_atime", "st_birthtime",),
            lambda timet: datetime.fromtimestamp(timet).isoformat()),
        (("st_mode",), oct),
    ):
        for k in keys:
            value = attr.pop(k, None)
            if value is not None:
                lines.append(k + ": " + formatter(value))
    # Keys not explicitly above
    for k, v in attr.items():
        lines.append(k + ": " + str(v))
    return "\n".join(lines)


class DockerModel(_DockerModel):

    tags: Iterable[str]


class CachingDockerContext():

    client: docker.client.DockerClient
    volume_symlinks: Dict[str, str]
    image_symlinks: Dict[str, str]
    container_symlinks: Dict[str, str]
    file_desciptors: List[Optional[DockerModel]]

    # Linux: 'unix://var/run/docker.sock'
    # Mac colima: "unix:~/.colima/default/docker.sock"
    def __init__(self, base_url: str | None = None):
        self.client = docker.client.DockerClient(base_url=base_url)
        self.volume_symlinks = {}
        self.image_symlinks = {}
        self.container_symlinks = {}
        self.file_desciptors = [None] * 100

    ROOT_FOLDERS: Final = (
      ".",
      "..",
      "volumes",
      "images",
      "containers",
    )

    # sym-link calls

    def readlink(self, name: str) -> str:
        parts = name.split('/')
        assert len(parts) == 3
        assert parts[0] == ''
        symlinks = {
            "volumes": self.volume_symlinks,
            "images": self.image_symlinks,
            "containers": self.container_symlinks,
        }[parts[1]]
        dest_name = symlinks[parts[2]]
        return dest_name

    # `readdir` calls

    def readdir_(self) -> Generator[str,None,None]:
        yield from self.__class__.ROOT_FOLDERS

    def readdir_volumes(self) -> Generator[str,None,None]:
        syms : Dict[str, str] = {}
        self.volume_symlinks = syms
        for i in self.client.volumes.list():
            name = i.name
            yield name
            id = i.id
            if id.startswith("sha256:"):
                id = id[7:]
            if id != name:
                id = '.' + id
                yield id
                syms[name] = id

    def readdir_images(self) -> Generator[str,None,None]:
        syms : Dict[str, str] = {}
        self.image_symlinks = syms
        for i in self.client.images.list(all=True):
            id = i.id
            assert id.startswith("sha256:")
            id = '.' + id[7:]
            yield id
            syms.update({ t: id for t in i.tags })
            yield from i.tags

    def readdir_containers(self) -> Generator[str,None,None]:
        syms : Dict[str, str] = {}
        self.container_symlinks = syms
        for i in self.client.containers.list(all=True):
            name = i.name
            id = '.' + i.id
            syms[name] = id
            yield name
            yield id


    # `getattr` calls

    def getattr_(
        self,
        is_file: bool = False,
        mode: Optional[int] = None,
        atime: Optional[float] = None,
        ctime: Optional[float] = None,
        mtime: Optional[float] = None,
        size: int = 1000,
    ) -> FileAttra:
        """Called for the root of the file system, and as a base for when getting file and directory attras."""
        now_ish = float(1707020058.716742869)
        attr : FileAttra = {
          'st_atime': atime or now_ish,
          'st_ctime': ctime or now_ish,
          'st_uid': 0, # 0 == root
          'st_gid': 0, # 0 == root
          'st_mode': mode if mode else S_IRALL | (S_IFREG if is_file else S_IFDIR | S_IXALL),
          'st_mtime': mtime or now_ish,
          'st_nlink': 1 if is_file else 2,
        }
        # if size:
        attr['st_size'] = size or 1000
        if sys.platform == "darwin":
            attr["st_flags"] = 0  # user defined flags for file

        return attr


    def _find_from_name(self, collection: DockerCollection, name: str) -> DockerModel:
        model: DockerModel
        if name[0] == '.':
            name = name[1:] # "sha256:" +
        try:
            model = collection.get(name)
        except docker.errors.NotFound as e:
            logger.warning("Can't find '%s'.", name)
            raise FuseOSError(errno.ENOENT)
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


    def _getattr_from_model(self, collection: DockerCollection, name: str) -> FileAttra:
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


    def _getattr_from_collection(self, collection: DockerCollection, **list_kwargs) -> FileAttra:
        attr = self.getattr_(is_file=False).copy()
        ctime = attr["st_ctime"]
        size = 0
        for model in collection.list(**list_kwargs):
            attrs = model.attrs
            created : str = attrs.get("Created") or attrs.get("CreatedAt")
            this_ctime = datetime.fromisoformat(created).timestamp()
            if this_ctime > ctime:
                ctime = this_ctime
            size += attrs.get("Size", 0)
        attr["st_ctime"] = ctime
        attr["st_mtime"] = ctime
        attr["st_atime"] = ctime
        # attr["st_birthtime"] = ctime
        attr["st_size"] = size or 1000 # TODO: fake for fuse-t
        return attr


    def _getattr(self, collection: DockerCollection, name: Optional[str], **list_kwargs) -> FileAttra:
        attr = (
            self._getattr_from_model(collection, name)
            if name else
            self._getattr_from_collection(collection, **list_kwargs)
        )
        return attr

    def getattr_volumes(self, name: Optional[str]) -> FileAttra:
        return self._getattr(self.client.volumes, name)

    def getattr_images(self, name: Optional[str]) -> FileAttra:
        return self._getattr(self.client.images, name, all=True)

    def getattr_containers(self, name: Optional[str]) -> FileAttra:
        return self._getattr(self.client.containers, name, all=True)


    # Reading files

    def open(self, path: str, flags: int) -> int:
        # Find first empty file desciptor
        logger.info(f"open(self, {path=}, {flags=})")
        model = self._find_from_path(path)
        idx = self.file_desciptors.index(None, 3)
        self.file_desciptors[idx] = model
        return idx

    def read(self, path: str, length: int, offset, fh) -> bytes:
        logger.info(f"read(self, {path=}, {length=}, {offset=}, {fh=})")
        # The reality is that we need the size in mt_size to be "accurate" for
        # actual file reading (e.g. `cat` to work correctly.)
        return "Hello from Docker\n".encode("utf-8")

    def release(self, path: str, fh) -> int:
        logger.info(f"release(self, {path=}, {fh=})")
        assert self.file_desciptors[fh] is not None
        self.file_desciptors[fh] = None
        return 0
