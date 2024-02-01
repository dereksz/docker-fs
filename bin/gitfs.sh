#!/bin/sh

set -eu

GIT_ROOT=$(dirname $(readlink -f "$0"))/..
source "$GIT_ROOT/.venv/bin/activate"
nohup "$GIT_ROOT/src/gitconfigfs.py" "$@" >> "$GIT_ROOT/logs/gitconfigfs.log" 2>&1 &