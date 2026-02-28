"""Full calculator tool for deterministic mathematical evaluation.

Why: Agents need accurate, deterministic math calculations for business operations,
data analysis, and financial computations. This tool converts probabilistic LLM math
into precise, verifiable results.

Tradeoff: Uses numexpr for safe evaluation (prevents code injection) vs eval().
Alternative considered: ast.literal_eval (too restrictive, no math functions).

Design decisions:
- Supports full PEMDAS (Parentheses, Exponents, Multiplication, Division, Addition, Subtraction)
- Business calculator functions: percentage, rounding, min/max, abs, sqrt
- Safe evaluation using numexpr (no arbitrary code execution)
- Comprehensive error handling with clear messages
- Supports both integer and float operations
- Handles edge cases (division by zero, invalid expressions, etc.)

Use case: Agent needs to calculate percentages, averages, totals, financial metrics,
or any deterministic mathematical operation.
"""

import logging
import math
from typing import Union
from pydantic_ai import RunContext

from app.tools import register_tool

logger = logging.getLogger(__name__)

# Try to import numexpr for safe evaluation
try:
    import numexpr as ne
    HAS_NUMEXPR = True
except ImportError:
    HAS_NUMEXPR = False
    logger.warning(
        "numexpr not installed. Install with: pip install numexpr. "
        "Falling back to limited evaluation."
    )


@register_tool("calculator")
def calculator(
    ctx: RunContext,
    expression: str,
) -> float:
    """Evaluate mathematical expressions with full PEMDAS and business calculator functions.

    Why: Agents often need to perform precise calculations for business analysis,
    financial computations, data processing, and statistical operations. This tool
    provides deterministic results that agents can rely on.

    This tool supports:
    - PEMDAS operations: Parentheses, Exponents, Multiplication, Division, Addition, Subtraction
    - Basic arithmetic: +, -, *, /, %, **
    - Business functions: sqrt(), abs(), min(), max(), round()
    - Percentage calculations: (value / total) * 100
    - Complex expressions with proper order of operations

    Use this tool when:
    - You need to calculate percentages, averages, or totals
    - You need precise financial calculations (revenue, costs, margins)
    - You need to verify or correct mathematical computations
    - You need deterministic results (not probabilistic estimates)
    - You need to evaluate complex mathematical expressions

    Args:
        ctx: Pydantic AI context (not used, but required by tool protocol)
        expression: Mathematical expression to evaluate. Supports:
            - Basic operations: "100 + 50", "25 * 4", "100 / 5"
            - PEMDAS: "(10 + 5) * 2", "2 + 3 * 4", "(100 - 20) / 4"
            - Exponents: "2 ** 8", "10 ** 2", "sqrt(144)"
            - Functions: "sqrt(144)", "abs(-50)", "round(3.14159, 2)"
            - Percentages: "(25 / 100) * 100", "100 * 0.15"
            - Complex: "((100 + 50) * 1.15) - 10"

    Returns:
        Float result of the calculation

    Examples:
        >>> # Basic arithmetic
        >>> calculator(ctx, "100 + 50")  # 150.0
        >>> calculator(ctx, "25 * 4")  # 100.0
        >>> calculator(ctx, "100 / 5")  # 20.0

        >>> # PEMDAS (order of operations)
        >>> calculator(ctx, "(10 + 5) * 2")  # 30.0
        >>> calculator(ctx, "2 + 3 * 4")  # 14.0 (not 20!)
        >>> calculator(ctx, "(100 - 20) / 4")  # 20.0

        >>> # Exponents
        >>> calculator(ctx, "2 ** 8")  # 256.0
        >>> calculator(ctx, "10 ** 2")  # 100.0

        >>> # Square root
        >>> calculator(ctx, "sqrt(144)")  # 12.0
        >>> calculator(ctx, "sqrt(25)")  # 5.0

        >>> # Absolute value
        >>> calculator(ctx, "abs(-50)")  # 50.0

        >>> # Rounding
        >>> calculator(ctx, "round(3.14159, 2)")  # 3.14

        >>> # Percentages
        >>> calculator(ctx, "(25 / 100) * 100")  # 25.0
        >>> calculator(ctx, "100 * 0.15")  # 15.0

        >>> # Complex business calculations
        >>> calculator(ctx, "((100 + 50) * 1.15) - 10")  # 162.5
        >>> calculator(ctx, "(35 + 28 + 22) / 3")  # 28.333...

        >>> # Financial calculations
        >>> calculator(ctx, "1000 * (1 + 0.05) ** 2")  # Compound interest
        >>> calculator(ctx, "(500 - 350) / 500 * 100")  # Profit margin %

    Raises:
        ValueError: If expression is invalid, contains unsafe operations, or results in error
        ZeroDivisionError: If division by zero occurs (handled gracefully)
    """
    if not expression or not expression.strip():
        raise ValueError("Expression cannot be empty")

    # Clean and prepare expression
    expression = expression.strip()

    # Basic validation: check for potentially dangerous patterns
    # (numexpr handles this, but we add extra safety)
    dangerous_patterns = [
        "__",
        "import ",
        "exec(",
        "eval(",
        "open(",
        "file(",
    ]
    for pattern in dangerous_patterns:
        if pattern in expression.lower():
            raise ValueError(
                f"Expression contains potentially unsafe pattern: {pattern}. "
                "Only mathematical operations are allowed."
            )

    try:
        if HAS_NUMEXPR:
            # Use numexpr for safe, fast evaluation
            # numexpr supports: +, -, *, /, %, **, and common functions
            # It also handles order of operations (PEMDAS) correctly

            # Add common math functions that numexpr supports
            # Note: numexpr has limited function support, so we handle some manually
            # For functions not in numexpr, we'll use Python's math module

            # Replace common function calls that numexpr doesn't support directly
            # We'll evaluate the expression and then apply functions if needed
            result = _evaluate_with_functions(expression)

        else:
            # Fallback: limited safe evaluation
            # Only allow basic operations for security
            result = _evaluate_safe_fallback(expression)

        # Convert to float and return
        result_float = float(result)

        logger.debug(
            f"Calculator evaluated: {expression} = {result_float}",
            extra={"expression": expression, "result": result_float}
        )

        return result_float

    except ZeroDivisionError:
        error_msg = f"Division by zero in expression: {expression}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    except Exception as e:
        error_msg = f"Error evaluating expression '{expression}': {str(e)}"
        logger.error(
            error_msg,
            extra={"expression": expression},
            exc_info=True
        )
        raise ValueError(error_msg)


def _evaluate_with_functions(expression: str) -> Union[int, float]:
    """Evaluate expression with support for common functions.

    Why: numexpr has limited function support, so we handle common business
    calculator functions manually by preprocessing the expression.

    Strategy: Process function calls from innermost to outermost, replacing
    them with their evaluated values before passing to numexpr.
    """
    import re

    # Process functions iteratively until no more function calls remain
    max_iterations = 100  # Prevent infinite loops
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        original_expression = expression

        # Find innermost function calls (no nested parentheses in arguments)
        # Handle sqrt() function
        sqrt_pattern = r'sqrt\(([^()]+)\)'
        match = re.search(sqrt_pattern, expression)
        if match:
            inner_expr = match.group(1)
            inner_result = ne.evaluate(inner_expr).item()
            sqrt_result = math.sqrt(inner_result)
            expression = expression.replace(match.group(0), str(sqrt_result), 1)
            continue

        # Handle abs() function
        abs_pattern = r'abs\(([^()]+)\)'
        match = re.search(abs_pattern, expression)
        if match:
            inner_expr = match.group(1)
            inner_result = ne.evaluate(inner_expr).item()
            abs_result = abs(inner_result)
            expression = expression.replace(match.group(0), str(abs_result), 1)
            continue

        # Handle round() function - format: round(value, digits)
        round_pattern = r'round\(([^,()]+),\s*(\d+)\)'
        match = re.search(round_pattern, expression)
        if match:
            value_expr = match.group(1)
            digits = int(match.group(2))
            value_result = ne.evaluate(value_expr).item()
            round_result = round(value_result, digits)
            expression = expression.replace(match.group(0), str(round_result), 1)
            continue

        # Handle min() function (2 arguments)
        min_pattern = r'min\(([^,()]+),\s*([^,()]+)\)'
        match = re.search(min_pattern, expression)
        if match:
            val1_expr = match.group(1)
            val2_expr = match.group(2)
            val1 = ne.evaluate(val1_expr).item()
            val2 = ne.evaluate(val2_expr).item()
            min_result = min(val1, val2)
            expression = expression.replace(match.group(0), str(min_result), 1)
            continue

        # Handle max() function (2 arguments)
        max_pattern = r'max\(([^,()]+),\s*([^,()]+)\)'
        match = re.search(max_pattern, expression)
        if match:
            val1_expr = match.group(1)
            val2_expr = match.group(2)
            val1 = ne.evaluate(val1_expr).item()
            val2 = ne.evaluate(val2_expr).item()
            max_result = max(val1, val2)
            expression = expression.replace(match.group(0), str(max_result), 1)
            continue

        # No more function calls found, break
        if expression == original_expression:
            break

    if iteration >= max_iterations:
        raise ValueError("Expression too complex or contains circular function calls")

    # Evaluate the final expression with numexpr
    # numexpr handles: +, -, *, /, %, **, and proper PEMDAS order
    result = ne.evaluate(expression).item()

    return result


def _evaluate_safe_fallback(expression: str) -> Union[int, float]:
    """Fallback evaluation when numexpr is not available.

    Why: Graceful degradation - still works but with limited function support.
    Tradeoff: Less safe than numexpr, but better than nothing.
    """
    import ast
    import operator

    # Only allow basic operations
    allowed_operators = {
        ast.Add: operator.add,
        ast.Sub: operator.sub,
        ast.Mult: operator.mul,
        ast.Div: operator.truediv,
        ast.Pow: operator.pow,
        ast.Mod: operator.mod,
        ast.USub: operator.neg,
    }

    def eval_node(node):
        """Safely evaluate AST node."""
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.BinOp):
            left = eval_node(node.left)
            right = eval_node(node.right)
            op = allowed_operators.get(type(node.op))
            if op is None:
                raise ValueError(f"Operator {type(node.op)} not allowed")
            return op(left, right)
        elif isinstance(node, ast.UnaryOp):
            operand = eval_node(node.operand)
            op = allowed_operators.get(type(node.op))
            if op is None:
                raise ValueError(f"Operator {type(node.op)} not allowed")
            return op(operand)
        else:
            raise ValueError(f"Node type {type(node)} not allowed")

    # Parse and evaluate
    tree = ast.parse(expression, mode='eval')
    result = eval_node(tree.body)

    return result


__all__ = ["calculator"]

