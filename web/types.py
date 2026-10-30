from dataclasses import dataclass


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    errors: list[str]
