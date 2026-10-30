import pytest

from web.services.privacy import redact_paths


@pytest.mark.parametrize("path", [
    r"C:\Users\runner\private\stdout.log",
    r"C:/Program Files/CQ4OE/private/stdout.log",
    r"\\build-host\share name\CQ4OE\stdout.log",
    "/tmp/runner workspace/CQ4OE/stdout.log",
])
def test_redacts_platform_absolute_paths_without_eating_surrounding_text(path):
    message = f"before {path}; after details"
    safe = redact_paths(message)
    assert path not in safe
    assert safe.startswith("before [workspace path];")
    assert safe.endswith("after details")
