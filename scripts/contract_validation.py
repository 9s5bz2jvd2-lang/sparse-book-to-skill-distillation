#!/usr/bin/env python3
"""Small JSON-Schema subset validator used by the local reference implementation.

It intentionally supports only the keywords used by contracts/*.schema.json.  This
keeps validation deterministic and dependency-free; it is not a general JSON
Schema implementation.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

CONTRACT_VERSION = "2.0.0"


class ContractError(ValueError):
    """A stable, user-facing contract validation failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def as_dict(self) -> dict[str, str]:
        return {"error": self.code, "message": self.message}


def load_json(path: Path) -> Any:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ContractError("invalid_json", f"cannot read JSON {path}: {exc}") from exc


def _matches_type(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    raise ContractError("unsupported_schema_keyword", f"unsupported type {expected!r}")


def validate_instance(value: Any, schema: dict[str, Any], path: str = "$") -> None:
    """Validate an instance against the repository's deliberately small schema subset."""

    expected_type = schema.get("type")
    if expected_type is not None and not _matches_type(value, expected_type):
        raise ContractError("malformed_input", f"{path}: expected {expected_type}")

    if "const" in schema and value != schema["const"]:
        code = "schema_version_mismatch" if path.endswith("contract_version") else "malformed_input"
        raise ContractError(code, f"{path}: expected constant {schema['const']!r}")

    if "enum" in schema and value not in schema["enum"]:
        raise ContractError("malformed_input", f"{path}: value {value!r} is not allowed")

    if isinstance(value, dict):
        required = schema.get("required", [])
        missing = [key for key in required if key not in value]
        if missing:
            raise ContractError("malformed_input", f"{path}: missing required fields {missing}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extras = sorted(set(value) - set(properties))
            if extras:
                raise ContractError("malformed_input", f"{path}: unexpected fields {extras}")
        for key, item in value.items():
            if key in properties:
                validate_instance(item, properties[key], f"{path}.{key}")

    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            raise ContractError("malformed_input", f"{path}: too few items")
        if schema.get("uniqueItems"):
            fingerprints = [json.dumps(item, ensure_ascii=False, sort_keys=True) for item in value]
            if len(fingerprints) != len(set(fingerprints)):
                raise ContractError("malformed_input", f"{path}: items must be unique")
        item_schema = schema.get("items")
        if item_schema:
            for index, item in enumerate(value):
                validate_instance(item, item_schema, f"{path}[{index}]")

    if isinstance(value, str):
        if len(value) < schema.get("minLength", 0):
            raise ContractError("malformed_input", f"{path}: string is too short")
        maximum = schema.get("maxLength")
        if maximum is not None and len(value) > maximum:
            raise ContractError("malformed_input", f"{path}: string is too long")
        pattern = schema.get("pattern")
        if pattern and re.search(pattern, value) is None:
            raise ContractError("malformed_input", f"{path}: value does not match {pattern!r}")

    if isinstance(value, int) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise ContractError("malformed_input", f"{path}: value is below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            raise ContractError("malformed_input", f"{path}: value is above maximum")
