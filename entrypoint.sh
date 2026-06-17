#!/bin/bash
set -e

# ChromaDB index + SQLite schema are pre-built into the image during docker build.
# No setup needed at runtime — just start the service directly.
exec "$@"
