# Docker FS

## Summary

The intention of Docker FS is to expose information
about Docker objects (containers, images, volumes, etc.) via
a FUSE (Filesystem in USEr-space) mount point.

## Motivation

When using GNU Makefiles to build development 
assets, whether items need to be rebuilt is done base on
comparing the date/time stamp of the target **file**, with 
the date/time stamps of the **files** on which that item 
depends.

The problem here is that Docker does not expose the
assets it builds as files.  If you want to know about
Docker objects, you need to run the appropriate `docker`
command.  E.g., to get a list of Dockers containers, 
you need to run `docker container ls -a --format json`
to extract all of the information.