import json
import shutil
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[2]


def test_compose_binds_host_data_directory():
    if not shutil.which("docker"):
        pytest.skip("Docker Compose is unavailable")
    result = subprocess.run(["docker", "compose", "config", "--format", "json"],
                            cwd=ROOT, capture_output=True, text=True, check=True)
    app = json.loads(result.stdout)["services"]["app"]
    mount = next(volume for volume in app["volumes"] if volume["target"] == "/app/data")
    assert mount["type"] == "bind"
    assert Path(mount["source"]).resolve() == (ROOT / "data").resolve()


def test_entrypoint_fixes_root_owned_bind_and_drops_to_app_user(tmp_path):
    if not shutil.which("docker"):
        pytest.skip("Docker is unavailable")
    image = "python:3.10-slim-bookworm"
    available = subprocess.run(["docker", "image", "inspect", image], capture_output=True)
    if available.returncode:
        pytest.skip("Local Python base image is unavailable")

    data = tmp_path / "data"
    data.mkdir()
    helpers = tmp_path / "helpers"
    helpers.mkdir()
    (helpers / "gosu").write_bytes(
        b"#!/bin/sh\n"
        b"[ \"$1\" = cq4oe ] || exit 12\n"
        b"exec su -s /bin/sh -c 'id -u > /app/data/runtime-uid; touch /app/data/runtime-write' cq4oe\n"
    )
    command = (
        "groupadd -g 10001 cq4oe && useradd -u 10001 -g 10001 -M cq4oe && "
        "cp /helpers/gosu /usr/local/bin/gosu && chmod +x /usr/local/bin/gosu && "
        "chown root:root /app/data && "
        "CQ4OE_DATA_DIR=/app/data sh /source/docker/entrypoint.sh"
    )
    result = subprocess.run([
        "docker", "run", "--rm", "--pull=never",
        "--mount", f"type=bind,source={ROOT},target=/source,readonly",
        "--mount", f"type=bind,source={data},target=/app/data",
        "--mount", f"type=bind,source={helpers},target=/helpers",
        image, "sh", "-c", command,
    ], capture_output=True, text=True, timeout=15)
    assert result.returncode == 0, result.stderr
    assert (data / "runtime-uid").read_text(encoding="utf-8").strip() == "10001"
    assert (data / "runtime-write").is_file()
