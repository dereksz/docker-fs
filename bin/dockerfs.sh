#!/bin/sh

set -eu

GIT_ROOT=$(dirname $(readlink -f "$0"))/..
source "$GIT_ROOT/.venv/bin/activate"
nohup $GIT_ROOT/src/dockerfs.py "$@" >> "$GIT_ROOT/logs/dockerfs.log" 2>&1 &
