#!/bin/sh
set -eu

data_dir=${CQ4OE_DATA_DIR:-/app/data}
mkdir -p "$data_dir"
chown -R 10001:10001 "$data_dir"

exec gosu cq4oe uvicorn web.app:app --host 0.0.0.0 --port 8000
