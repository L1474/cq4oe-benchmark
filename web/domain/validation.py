from pathlib import Path

from web.domain.catalog import _cq_file, _load_cqs
from web.types import ValidationResult


def validate_cq_term_prediction(
    project_root: Path, domain: str, payload: object
) -> ValidationResult:
    expected = [cq["id"] for cq in _load_cqs(_cq_file(project_root, "cq2term", domain))]
    errors = []
    if not isinstance(payload, list):
        return ValidationResult(False, ["Prediction must be a JSON list."])

    received = []
    for index, row in enumerate(payload):
        if not isinstance(row, dict):
            errors.append(f"Row {index} must be an object.")
            continue
        cq_id = row.get("id")
        if not isinstance(cq_id, str) or not cq_id:
            errors.append(f"Row {index} must have a non-empty string id.")
        else:
            received.append(cq_id)
        for field in ("class", "property"):
            terms = row.get(field)
            if not isinstance(terms, list) or any(not isinstance(term, str) for term in terms):
                errors.append(f"Row {index} field {field!r} must be a list of strings.")

    duplicates = sorted({cq_id for cq_id in received if received.count(cq_id) > 1})
    unknown = sorted(set(received) - set(expected))
    missing = sorted(set(expected) - set(received))
    if duplicates:
        errors.append(f"Duplicate CQ IDs: {', '.join(duplicates)}.")
    if unknown:
        errors.append(f"Unknown CQ IDs: {', '.join(unknown)}.")
    if missing:
        errors.append(f"Missing CQ IDs: {', '.join(missing)}.")
    return ValidationResult(not errors, errors)


def validate_cq2onto_confirmation(
    project_root: Path, domain: str, confirmed_ids: list[str]
) -> ValidationResult:
    expected = [cq["id"] for cq in _load_cqs(_cq_file(project_root, "cq2onto", domain))]
    errors = []
    if not isinstance(confirmed_ids, list) or any(not isinstance(item, str) for item in confirmed_ids):
        return ValidationResult(False, ["Confirmed CQ IDs must be a list of strings."])
    duplicates = sorted({cq_id for cq_id in confirmed_ids if confirmed_ids.count(cq_id) > 1})
    unknown = sorted(set(confirmed_ids) - set(expected))
    missing = sorted(set(expected) - set(confirmed_ids))
    if duplicates:
        errors.append(f"Duplicate CQ IDs: {', '.join(duplicates)}.")
    if unknown:
        errors.append(f"Unknown CQ IDs: {', '.join(unknown)}.")
    if missing:
        errors.append(f"Missing CQ IDs: {', '.join(missing)}.")
    return ValidationResult(not errors, errors)
