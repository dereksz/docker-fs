# Not a build system, but a command-runner-helper

.PHONY: run ls

run:
	docker run --rm bash ls

ls:
	docker image ls --format jsoncd ../..