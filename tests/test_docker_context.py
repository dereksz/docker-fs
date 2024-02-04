

import pytest
from rich import inspect

from caching_docker_context import CachingDockerContext

@pytest.fixture
def docker():
    return CachingDockerContext()

def test_ls_volumes(docker: CachingDockerContext):
    volumes = docker.readdir_volumes()
    print(inspect(volumes))
    return volumes

def test_ls_images(docker: CachingDockerContext):
    images = docker.readdir_images()
    print(inspect(images))
    return images

def test_ls_containers(docker: CachingDockerContext):
    containers = docker.readdir_containers()
    print(inspect(containers))
    return containers

def main():
    docker = CachingDockerContext()
    test_ls_volumes(docker)
    test_ls_images(docker)
    test_ls_containers(docker)
    
if __name__ == "__main__":
    main()