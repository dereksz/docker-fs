# DockerFS

## Summary

The intention of DockerFS is to expose information
about Docker objects (containers, images, volumes, etc.) via
a [FUSE (Filesystem in USEr-space)](https://en.wikipedia.org/wiki/Filesystem_in_Userspace)
mount point.

## Motivation

When using GNU Makefiles to build development 
assets, whether items need to be rebuilt is done base on
comparing the date/time stamp of the target **file**, with 
the date/time stamps of the **files** on which that item 
depends.

The problem here is that Docker does not expose the
assets it builds as files.  If you want to know about
Docker objects, you need to run the appropriate `docker`
command.  E.g., to get a list of Docker containers, 
you need to run `docker container ls -a --format json`
to extract that information.

The idea of Docker FS is that it exposes this data as
files under a viurtual file-system so that `make` can 
use the Docker assets as if they were file targets
(the only kind of target that GNU `make` really supports).

### Resources

- [Example FUSE Loopback in Python](https://github.com/skorokithakis/python-fuse-sample)
- [TTL Cache](https://stackoverflow.com/a/52128389/1331446)
  to avoid calling Docker too often.  (Should likely be using
  soimething in the order of a second or two; time to re-invoke
  `make` is my thinking here.)



## Additionally: GitConfigFS

When using `docker compose`, the assets that are built are
predominantly copnfigured by only a small section of the 
`docker-compose.yml` file, that under `/services/<name>`
(as well as potentioally other sections like `/network`
and `/volumes` - but these will likely chage far less
frequently).

With this information, rebuilds are only necessary if
certain _parts_ of the `docker-compose.yml` file have
changes.

The purpose of the GitConfigFS is to expose `yml` / `yaml`
files as _folders_, which containfolders of the top level
keys, which contain folders of the next-level keys, etc..

So, why is "Git" in the name?  Well, using a `git blame` we can
find when each line of the file was changes (nearly).  We can then
use the date/time of the most recently change line as the
date/time of the folder, so that Makefiles can specify the
section(s) of the (e.g.) `docker-compose.yml` on which the
target depends.  ("Nearly" because uncommitted changes will
all have the files current date/time stamp; we can't track
date/time changes with finer granmularity.)

We could (in the future) look to expand this to inclue
section of (lines of) an `.ini` file, or other config file
formats.  Although supporting pure JSON be awkward as it is
often not stored in a line oriented format.

This driver will provide a read-only "loop-back" driver 
that effectively bind-mounts and existing file system, 
_except_ when the file is a `yml` / `yaml` file, when
the above behaviour will be used instead.

### Resources

- [Getting line numbers while parsing YAML](https://stackoverflow.com/a/53647080/1331446)
- [Example FUSE Loopback in Python](https://github.com/skorokithakis/python-fuse-sample)
