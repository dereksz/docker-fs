from typing import Final, Generator, Sequence
import docker
from docker.client import DockerClient


class CachingDockerContext(docker.client.DockerClient):
  
    def __init__(self):
        docker.client.DockerClient.__init__(self, base_url='unix://var/run/docker.sock')
        
    ROOT_FOLDERS: Final = (
      ".",
      "..",
      "volumes",
      "images",
      "containers",
    ) 
    
    # 
    
    def readdir_(self) -> Sequence[str]:
        return self.__class__.ROOT_FOLDERS
        
    def readdir_volumes(self) -> Sequence[str]:
        for i in self.volumes.list():
          assert i.id.startswith("sha256:")
          yield '.' + i.id[7:]

    def readdir_images(self) -> Generator[str,None,None]:
        for i in self.images.list():
          assert i.id.startswith("sha256:")
          yield '.' + i.id[7:]

    def readdir_containers(self) -> Sequence[str]:
        for i in self.containers.list():
          assert i.id.startswith("sha256:")
          yield '.' + i.id[7:]
        
        
    def getattr_(self) -> Sequence[str]:
        now_ish = float(1707020058.716742869)
        attr = {
          'st_atime': now_ish,
          'st_ctime': now_ish,
          'st_uid': 0, # 0 == root
          'st_gid': 0, # 0 == root
          'st_mode': 0o40555,
          'st_mtime': now_ish,
          'st_nlink': 1,
          'st_size': 100,
        }
        return attr

        
    def getattr_volumes(self) -> Sequence[str]:
        for i in self.volumes.list():
          assert i.id.startswith("sha256:")
          yield '.' + i.id[7:]

    def getattr_images(self) -> Generator[str,None,None]:
        for i in self.images.list():
          assert i.id.startswith("sha256:")
          yield '.' + i.id[7:]

    def getattr_containers(self) -> Sequence[str]:
        for i in self.containers.list():
          assert i.id.startswith("sha256:")
          yield '.' + i.id[7:]        