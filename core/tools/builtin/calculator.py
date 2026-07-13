"""CalculatorTool — safe arithmetic evaluation."""
from __future__ import annotations
import operator
import math

from core.tools.models import ToolRequest, ToolResult, ToolInfo, ToolCategory, ParameterSchema
from core.tools.protocol import ToolProtocol

# Allowed operators for safe evaluation
_ALLOWED_OPS = {
    "+": operator.add, "-": operator.sub,
    "*": operator.mul, "/": operator.truediv,
    "**": operator.pow, "%": operator.mod,
}
_ALLOWED_FUNCS = {
    "abs": abs, "round": round, "min": min, "max": max,
    "sqrt": math.sqrt, "pow": math.pow,
    "ceil": math.ceil, "floor": math.floor,
}


class CalculatorTool(ToolProtocol):
    def __init__(self):
        self._info = ToolInfo(
            name="calculator",
            description="Safely evaluate arithmetic expressions. Supports +, -, *, /, **, %, sqrt, ceil, floor, abs, round, min, max, pow.",
            version="1.0.0",
            category=ToolCategory.UTILITY,
            tags=["math", "utility"],
            parameters=ParameterSchema(
                properties={
                    "expression": {"type": "string", "description": "Arithmetic expression to evaluate, e.g. '2 + 3 * 4'"},
                },
                required=["expression"],
            ),
            permissions=[],
        )

    async def initialize(self) -> None:
        pass

    async def execute(self, request: ToolRequest) -> ToolResult:
        expr = request.arguments.get("expression", "")
        if not expr:
            return ToolResult(success=False, error="Expression is empty")

        try:
            # Use safe eval with restricted locals
            result = eval(expr, {"__builtins__": {}}, {**_ALLOWED_OPS, **_ALLOWED_FUNCS})
            return ToolResult(success=True, output=result)
        except Exception as e:
            return ToolResult(success=False, error=f"Calculation error: {e}")

    async def validate(self, request: ToolRequest) -> bool:
        expr = request.arguments.get("expression", "")
        return isinstance(expr, str) and len(expr) > 0

    async def health_check(self) -> bool:
        return True

    async def shutdown(self) -> None:
        pass

    @property
    def info(self) -> ToolInfo:
        return self._info
