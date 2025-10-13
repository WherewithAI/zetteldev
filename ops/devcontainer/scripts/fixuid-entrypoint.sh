#!/bin/sh
set -eu
/usr/local/bin/fixuid -q
exec "$@"
