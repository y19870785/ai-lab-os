"""ToolValidator — JSON Schema validation for tool arguments."""
from __future__ import annotations
from typing import Any
from core.tools.models import ParameterSchema, ToolRequest, ToolInfo
from core.tools.exceptions import ToolValidationError

class ToolValidator:
    @staticmethod
    def validate(request: ToolRequest, info: ToolInfo) -> None:
        schema = info.parameters
        args = request.arguments
        for field in schema.required:
            if field not in args:
                raise ToolValidationError(f"Missing required parameter: {field}")
        for field, spec in schema.properties.items():
            if field in args:
                ToolValidator._check_type(field, args[field], spec)
    @staticmethod
    def _check_type(field: str, value: Any, spec: dict[str, Any]) -> None:
        expected = spec.get("type", "string")
        type_map = {"string": str, "integer": int, "number": (int, float), "boolean": bool, "array": list, "object": dict}
        expected_type = type_map.get(expected)
        if expected_type and not isinstance(value, expected_type):
            raise ToolValidationError(f"Parameter {field}: expected {expected}, got {type(value).__name__}")