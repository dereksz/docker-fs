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

After some false starts, the code was crafted to work with
[`fusepy`](https://pypi.org/project/fusepy/).  It works well 
on Linux, and on MacOS using [fuse-t](https://www.fuse-t.org/).

The script is self documenting.  But do note that - in particular - the
docker source and mount point are reversed from what you'd expect on a
`mount` command.  This is actually convenient, because the source is actually
something that is relatively easy for us to guess using calls into docker.
The target, less so.  My recomendation is that you hide it way in a folder
called `.dockerfs` and - after you've snooped around to see if you like it -
just let your makefiles reference the named assets in there.

As a design decision, assets named using a sha256 are prefixed with a `.`,
so that they are (by default) hiden from `ls`.  Named objects are listed 
as expected.  The tags used to described assets are also output (like names)
and show up a sym-links to the `.<sha256>` files.  Currently these include the 
`:latest`, etc., parts of the name, which may become problematic.
Names and tags with `/` in them are currently not being displayed.
I'm hesitent to try and fix this just yet due to the significant increase in 
complexity that would arise.  If you feel strongly abbout this and think you
have a solid solution design, please raise an issue and we can start a discussion.

I am **definitely** abusing the POSIX file system in this driver.


```
> src/dockerfs.py -h

usage: DockerFS [-h] [--verbose] [--quiet] [--debug-fuse] [mount_point] [docker_source]

Creates virtual file system exposing Docker asset names and dates.

positional arguments:
  mount_point    Mount point for docker virtual file system. Defaults to `.dockerfs`.
  docker_source  Socket or port to connect to docker, e.g. `unix:///var/run/docker.sock`.
                 Will ask and use dockers 'Host' from the default context is not supplied.

options:
  -h, --help     show this help message and exit
  --verbose, -v  Enables DEBUG level tracing
  --quiet, -q    Drops to WARNING level tracing
  --debug-fuse   Enables debugging in fusepy library.
```

The code initially was loosely based on code originally created by
[Stavros Korokithakis](https://github.com/skorokithakis):
    - https://www.stavros.io/posts/python-fuse-filesystem/
    - https://github.com/skorokithakis/python-fuse-sample


### Additional Resources

- [Example FUSE Loopback in Python](https://github.com/skorokithakis/python-fuse-sample)
- [TTL Cache](https://stackoverflow.com/a/52128389/1331446)
  to avoid calling Docker too often.  (Should likely be using
  something in the order of a second or two; time to re-invoke
  `make` is my thinking here.)



# Possible Future Work

## Additionally: GitConfigFS

When using `docker compose`, the assets that are built are
predominantly copnfigured by only a small section of the 
`docker-compose.yml` file, that under `/services/<name>`
(as well as potentioally other sections like `/network`
and `/volumes` - but these will likely change far less
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


## What else?

- What could we print if we were to `cat` the pseudo-files?
  - `docker inspect` (equivalent)?
  - file system contents if they were a volume?
