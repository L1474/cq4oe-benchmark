import re


_ABSOLUTE_START = re.compile(r"(?<![\w:])(?:[A-Za-z]:[\\/]|\\\\|/(?!/))")
_PATH_END = re.compile(r"\.[A-Za-z0-9]{1,12}(?=$|[\s,;)}\]])")
_HARD_DELIMITERS = frozenset(",;\r\n\"'<>|)}]")


def _redact_text(value: str) -> str:
    output = []
    cursor = 0
    while match := _ABSOLUTE_START.search(value, cursor):
        start = match.start()
        output.append(value[cursor:start])
        end = start
        while end < len(value) and value[end] not in _HARD_DELIMITERS:
            end += 1
        path_text = value[start:end]
        file_end = _PATH_END.search(path_text)
        if file_end:
            end = start + file_end.end()
        else:
            while end > start and value[end - 1].isspace():
                end -= 1
        if end == start:
            output.append(value[cursor:match.end()])
            cursor = match.end()
            continue
        output.append("[workspace path]")
        cursor = end
    output.append(value[cursor:])
    return "".join(output)


def redact_paths(value):
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, list):
        return [redact_paths(item) for item in value]
    if isinstance(value, dict):
        return {key: redact_paths(item) for key, item in value.items()}
    return value
