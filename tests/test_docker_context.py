

import pytest
from rich import inspect

from docker_context import DockerContext

@pytest.fixture
def docker():
    return DockerContext()

def test_ls_volumes(docker: DockerContext):
    volumes = docker.readdir_volumes()
    print(inspect(volumes))
    return volumes

def test_ls_images(docker: DockerContext):
    images = docker.readdir_images()
    print(inspect(images))
    return images

def test_ls_containers(docker: DockerContext):
    containers = docker.readdir_containers()
    print(inspect(containers))
    return containers

def main():
    docker = DockerContext()
    test_ls_volumes(docker)
    test_ls_images(docker)
    test_ls_containers(docker)

if __name__ == "__main__":
    main()
