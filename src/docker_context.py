"""Classes, methods, functions, and constants to help re-present docker assets as
file-system entities.  (Files, Folders, Sym-links, with appropriate attributes.)
"""
import sys
from typing import Dict, Final, Generator, Iterable, List, Optional, Set
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
from cachetools.func import ttl_cache

from file_attr import S_IRALL, S_IXALL, FileAttr


SHA256 = str

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
    api: docker.APIClient
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
        self.api = docker.APIClient(base_url=base_url)
        self.client = docker.client.DockerClient(base_url=base_url)
        self.volume_symlinks = {}
        self.image_symlinks = {}
        self.container_symlinks = {}


    ROOT_FOLDERS: Final = (
      "volumes",
      "images",
      "containers",
    )
    """These are the folders that are exposed at the root of the filesystem."""


    # sym-link calls

    def readlink(self, name: str) -> str:
        """Dereference a sym-link into a file name / path."""
        try:
            root, model_type, name_or_tag = name.split('/', maxsplit=2)
            assert root == ''
            symlinks = {
                "volumes": self.volume_symlinks,
                "images": self.image_symlinks,
                "containers": self.container_symlinks,
            }[model_type]
            dest_name = symlinks[name_or_tag]
            sub_dir_depth = name_or_tag.count("/")
            if sub_dir_depth > 0:
                dest_name = "../" * sub_dir_depth + dest_name
            return dest_name
        except Exception as e:
            raise FuseOSError(errno.ENOENT) from e


    # `readdir` calls

    def readdir_(self, tag_prefix=None) -> Generator[str,None,None]:
        """Generate folder names for filesystem root."""
        yield from self.__class__.ROOT_FOLDERS

    def readdir_volumes(self, tag_prefix=None) -> Generator[str,None,None]:
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

    def readdir_images(self, tag_prefix: str | None = None, sym_links_only = False) -> Generator[str,None,None]:
        """Generate image names and sha256's.
        
        The ``sym_links_only`` flag allows us to just generate the ``image_symlinks``
        attribute in situation where it may not yet have been created.
        """
        if tag_prefix is not None:
            yield from self.readdir_image_tags(tag_prefix)
            return
        syms : Dict[str, str] = {}
        self.image_symlinks = syms
        sub_dirs: Set[str] = set()
        for i in self.client.images.list(all=True):
            sha256 = i.id
            assert sha256.startswith("sha256:")
            sha256 = '.' + sha256[7:]
            syms.update({ t: sha256 for t in i.tags })
            if sym_links_only:
                continue
            t: str
            yield sha256
            for t in i.tags:
                LOGGER.info("Image tag: %s", t)
                try:
                    idx = t.index('/')
                except ValueError:
                    yield t # no sub-folders
                else:
                    # extract sub-folder
                    next_level_dir = t[:idx]
                    # check we've not handed it out already
                    if next_level_dir in sub_dirs:
                        continue
                    sub_dirs.add(next_level_dir)
                    yield next_level_dir
                

    def readdir_image_tags(self, tag_prefix: str) -> Generator[str,None,None]:
        if tag_prefix[-1] != '/':
            tag_prefix += '/'
        remaining_starts_at = len(tag_prefix)
        sub_dirs: Set[str] = set()
        if not self.image_symlinks:
            for _ in self.readdir_images(sym_links_only=True):
                pass
            
        for tag in self.image_symlinks:
            if tag.startswith(tag_prefix):
                tag_remaining = tag[remaining_starts_at:]
                if '/' in tag_remaining:
                    sub_dir, _ = tag_remaining.split("/", maxsplit=2)
                    if sub_dir not in sub_dirs:
                        sub_dirs.add(sub_dir)
                        yield sub_dir
                else:
                    yield tag_remaining
                
    def readdir_containers(self, tag_prefix=None) -> Generator[str,None,None]:
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
    
    @ttl_cache(ttl=2)
    def _get_sizes(self) -> Dict[SHA256, int]:
        result : Dict[SHA256, int] = {}
        df = self.api.df()
        for type in ("Containers",): # "Volumes", "Images"):
            resources = df.get(type)
            if not resources:
                continue
            for resource in resources:
                result[resource["Id"]] = (
                    resource.get("SizeRootFs")
                )
                
        return result
            

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
        attr : FileAttr = FileAttr(
          st_atime= atime or _OLD,
          st_ctime= ctime or _OLD,
          st_uid= 0, # 0 == root
          st_gid= 0, # 0 == root / wheel
          st_mode= mode if mode else S_IRALL | (S_IFREG if is_file else S_IFDIR | S_IXALL),
          st_mtime= mtime or _OLD,
          st_nlink= 1 if is_file else 2,
        )
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
        parts = path.split('/', maxsplit=3)

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


    def _getattr_from_name(self, collection: DockerCollection, name: str) -> FileAttr:
        model = self._find_from_name(collection, name)
        return self._getattr_from_model(model, name)


    def _getattr_from_model(self, model: DockerModel, name: str) -> FileAttr:
        attrs = model.attrs
        created : str = attrs.get("Created") or attrs.get("CreatedAt") # the latter for volumes
        ctime = datetime.fromisoformat(created).timestamp()
        size =  attrs.get("SizeRootFs") or attrs.get("Size") or self._get_sizes().get(model.id) or 1000
        # Get default attr
        attr = self.getattr_(is_file=True).copy()
        # And update
        attr["st_ctime"] = ctime
        attr["st_mtime"] = ctime
        attr["st_atime"] = ctime
        attr["st_birthtime"] = ctime
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
                # len of sha256 + 1 for leading '.' + any '../' for asscending
                attr["st_size"] = 64 + 1 + 3 * name.count('/')
        return attr


    def _getattr_from_collection(self, collection: DockerCollection, tag_prefix: str | None = None, **list_kwargs) -> FileAttr:
        attr = self.getattr_(is_file=False).copy()
        ctime = attr["st_ctime"]
        size = 0
        count = 0
        if tag_prefix and tag_prefix[-1] != '/':
            tag_prefix += '/'
        for model in collection.list(**list_kwargs):
            attrs = model.attrs
            if tag_prefix:
                if not any(t.startswith(tag_prefix) for t in model.tags):
                    continue
            created : str = attrs.get("Created") or attrs.get("CreatedAt")
            this_ctime = datetime.fromisoformat(created).timestamp()
            if this_ctime > ctime:
                ctime = this_ctime
            size += attrs.get("SizeRootFs", 0) or attrs.get("Size", 0)
            count += 1
        attr["st_ctime"] = ctime
        attr["st_mtime"] = ctime
        attr["st_atime"] = ctime
        attr["st_birthtime"] = ctime
        attr["st_size"] = size or 1000 # Fake for fuse. Zero can be problematic.
        attr["st_nlink"] += count # MacOS includes files in the nlink numbert too, we do that by default
        return attr


    def _getattr(
            self,
            collection: DockerCollection,
            name: Optional[str],
            **list_kwargs
    ) -> FileAttr:
        attr = (
            self._getattr_from_name(collection, name)
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
        or for the "images" folder (if ``name`` is None).
        """
        collection: Final = self.client.images
        if name:
            try:
                if name[0] == '.':
                    name = name[1:]
                model = collection.get(name)
            except docker.errors.NotFound as e:
                try_folder = name + '/'
                try:
                    result = self._getattr_from_collection(
                        collection, tag_prefix=try_folder, all=True)
                    if result["st_nlink"] > 2:
                        return result
                except Exception:
                    pass
                raise FuseOSError(errno.ENOENT) from e
            result = self._getattr_from_model(model, name)
        else:
            result = self._getattr_from_collection(collection, all=True)

        return result           


    def getattr_containers(self, name: Optional[str]) -> FileAttr:
        """Get attributes for a container (if ``name`` not None)
        or for the "containers" folder (if ``name`` is None).
        """
        containers = self.client.containers
        # containers = self.api.df()["Containers"]
        result = self._getattr(containers, name, all=True)
        if name:
            LOGGER.info("getattr_containers(%s) -> %s", name, result)
            a = 1
        return result



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


_OLD = float(0.0)
