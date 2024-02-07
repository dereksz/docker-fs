# Not a build system, but a command-runner-helper

MAKEFLAGS += --no-builtin-rules

.PHONY: run ls install install-clean setup

run:
	docker run bash ls
	docker run docker/whalesay Hello Derek

ls:
	docker image ls --format jsoncd ../..

.venv:
	python3.11 -m venv --system-site-packages .venv

setup: .venv
	source .venv/bin/activate && \
	pip install -r requirements.txt && \
	zsh -i


install-clean:
	sudo rm /usr/sbin/mount.dockerfs
	sudo rm /usr/sbin/mount.gitfs

# https://stackoverflow.com/a/1555146/1331446
install:
	sudo ln -s "$(PWD)/bin/dockerfs.sh" /usr/sbin/mount.dockerfs
	sudo ln -s "$(PWD)/bin/gitfs.sh" /usr/sbin/mount.gitfs
