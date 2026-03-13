"""Math and calculation tools."""

from __future__ import annotations

import ast
import operator
from typing import Any

from openagents.interfaces.tool import ToolPlugin
from openagents.interfaces.capabilities import TOOL_INVOKE


class CalcTool(ToolPlugin):
    """Simple calculator for basic operations."""

    # Safe operators
    OPS = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.Mod: operator.mod,
        ast.USub: operator.neg,
        ast.UAdd: operator.pos,
    }

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities={TOOL_INVOKE})

    def _eval_expr(self, node):
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.BinOp):
            left = self._eval_expr(node.left)
            right = self._eval_expr(node.right)
            op_type = type(node.op)
            if op_type in self.OPS:
                return self.OPS[op_type](left, right)
            raise ValueError(f"Unsupported operator: {op_type}")
        elif isinstance(node, ast.UnaryOp):
            op_type = type(node.op)
            if op_type in self.OPS:
                return self.OPS[op_type](self._eval_expr(node.operand))
            raise ValueError(f"Unsupported operator: {op_type}")
        raise ValueError(f"Unsupported expression: {ast.dump(node)}")

    def _safe_eval(self, expr):
        # Only allow numbers and operators
        allowed = set("0123456789.+-*/%() **")
        if any(c not in allowed for c in str(expr)):
            raise ValueError("Expression contains disallowed characters")
        try:
            tree = ast.parse(str(expr), mode="eval")
            return self._eval_expr(tree.body)
        except Exception as e:
            raise ValueError(f"Invalid expression: {e}")

    async def invoke(self, params: dict[str, Any], context: Any) -> Any:
        expression = params.get("expression", "")
        if not expression:
            raise ValueError("'expression' parameter is required")

        try:
            result = self._safe_eval(expression)
            return {"expression": expression, "result": result}
        except ValueError as e:
            raise ValueError(f"Calculation error: {e}")


class PercentageTool(ToolPlugin):
    """Percentage calculations."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities={TOOL_INVOKE})

    async def invoke(self, params: dict[str, Any], context: Any) -> Any:
        value = params.get("value", 0)
        percent = params.get("percent", 0)
        operation = params.get("operation", "of")  # of, increase, decrease

        try:
            value = float(value)
            percent = float(percent)
        except (TypeError, ValueError):
            raise ValueError("'value' and 'percent' must be numbers")

        if operation == "of":
            result = value * percent / 100
        elif operation == "increase":
            result = value * (1 + percent / 100)
        elif operation == "decrease":
            result = value * (1 - percent / 100)
        else:
            raise ValueError(f"Unknown operation: {operation}")

        return {
            "value": value,
            "percent": percent,
            "operation": operation,
            "result": result,
        }


class MinMaxTool(ToolPlugin):
    """Find min/max in numbers or list."""

    def __init__(self, config: dict[str, Any] | None = None):
        super().__init__(config=config or {}, capabilities={TOOL_INVOKE})

    async def invoke(self, params: dict[str, Any], context: Any) -> Any:
        numbers = params.get("numbers", [])
        action = params.get("action", "min")  # min, max, sum, avg, median

        if not numbers:
            raise ValueError("'numbers' parameter is required")

        if isinstance(numbers, str):
            try:
                numbers = [float(x.strip()) for x in numbers.split(",")]
            except ValueError:
                raise ValueError("'numbers' must be comma-separated numbers")

        try:
            numbers = [float(n) for n in numbers]
        except ValueError:
            raise ValueError("All values in 'numbers' must be numeric")

        if action == "min":
            result = min(numbers)
        elif action == "max":
            result = max(numbers)
        elif action == "sum":
            result = sum(numbers)
        elif action == "avg":
            result = sum(numbers) / len(numbers)
        elif action == "median":
            sorted_nums = sorted(numbers)
            n = len(sorted_nums)
            if n % 2 == 0:
                result = (sorted_nums[n // 2 - 1] + sorted_nums[n // 2]) / 2
            else:
                result = sorted_nums[n // 2]
        else:
            raise ValueError(f"Unknown action: {action}")

        return {"action": action, "numbers": numbers, "result": result}
