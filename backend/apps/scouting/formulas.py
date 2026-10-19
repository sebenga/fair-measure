"""Safe arithmetic for catalogue formulas, e.g. "goals * 90 / minutes".

Only numbers, names, + - * / and brackets are allowed. A formula never runs code.
"""

from __future__ import annotations

import ast
from decimal import Decimal, DivisionByZero, InvalidOperation

_OPERATORS = (ast.Add, ast.Sub, ast.Mult, ast.Div)


class FormulaError(ValueError):
    pass


def names(formula: str) -> set[str]:
    """Every name a formula uses; raises FormulaError if it is not plain arithmetic."""

    try:
        tree = ast.parse(formula, mode="eval")
    except SyntaxError as error:
        raise FormulaError(f"Not a formula: {formula!r}") from error
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Expression | ast.Load):
            continue
        if isinstance(node, ast.BinOp):
            if not isinstance(node.op, _OPERATORS):
                raise FormulaError(f"Only + - * / are allowed in {formula!r}")
        elif isinstance(node, ast.UnaryOp):
            if not isinstance(node.op, ast.USub | ast.UAdd):
                raise FormulaError(f"Only a leading minus is allowed in {formula!r}")
        elif isinstance(node, ast.Name):
            found.add(node.id)
        elif isinstance(node, ast.Constant):
            if not isinstance(node.value, int | float) or isinstance(node.value, bool):
                raise FormulaError(f"Only numbers are allowed in {formula!r}")
        elif not isinstance(node, (*_OPERATORS, ast.USub, ast.UAdd)):
            raise FormulaError(f"{type(node).__name__} is not allowed in {formula!r}")
    return found


def evaluate(formula: str, values: dict) -> Decimal | None:
    """The formula's value, or None when a value is missing or it divides by zero."""

    names(formula)
    tree = ast.parse(formula, mode="eval")

    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant):
            return Decimal(str(node.value))
        if isinstance(node, ast.Name):
            value = values.get(node.id)
            if value is None:
                raise KeyError(node.id)
            return Decimal(str(value))
        if isinstance(node, ast.UnaryOp):
            value = walk(node.operand)
            return -value if isinstance(node.op, ast.USub) else value
        left, right = walk(node.left), walk(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        return left / right

    try:
        return walk(tree)
    except (KeyError, DivisionByZero, InvalidOperation, ZeroDivisionError):
        return None
