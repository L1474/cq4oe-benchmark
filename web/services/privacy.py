import re


_ABSOLUTE_PATH = re.compile(r"(?i)(?:[a-z]:\\[^\s,;\"']+|/(?:[^\s/]+/)+[^\s,;\"']*)")


def redact_paths(value):
    if isinstance(value, str):
        return _ABSOLUTE_PATH.sub("[workspace path]", value)
    if isinstance(value, list):
        return [redact_paths(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_paths(item) for key, item in value.items()}
    return value
