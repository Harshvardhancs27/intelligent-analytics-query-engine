"""
Security Sandbox & AST Validator for generated Python analytics code.
Prevents code injection, unauthorized file access, process spawning, and dunder traversal.
"""
import ast
import logging
from typing import Set
from query_engine.config import BANNED_BUILTINS, BANNED_ATTRIBUTES

logger = logging.getLogger(__name__)


class SecurityViolationError(Exception):
    """Raised when generated code violates sandboxing security constraints."""
    pass


class ASTSecurityValidator(ast.NodeVisitor):
    """Inspects Python Abstract Syntax Trees for potentially malicious constructs."""

    def __init__(self):
        self.banned_names: Set[str] = set(BANNED_BUILTINS)
        self.banned_attrs: Set[str] = set(BANNED_ATTRIBUTES)

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            if alias.name not in {"pandas", "pd", "numpy", "np", "math"}:
                raise SecurityViolationError(f"Unauthorized import attempt: '{alias.name}'")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        if node.module not in {"pandas", "numpy", "math"}:
            raise SecurityViolationError(f"Unauthorized import from: '{node.module}'")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id in self.banned_names:
            raise SecurityViolationError(f"Execution of banned built-in function: '{node.func.id}'")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute):
        if node.attr in self.banned_attrs or node.attr.startswith("__"):
            raise SecurityViolationError(f"Access to restricted attribute or dunder: '{node.attr}'")
        self.generic_visit(node)


class SandboxValidator:
    """Validates generated code string prior to execution."""

    @classmethod
    def validate_code(cls, code_str: str) -> None:
        """Parses and validates Python code. Raises SecurityViolationError if invalid."""
        try:
            tree = ast.parse(code_str)
        except SyntaxError as e:
            raise SyntaxError(f"Generated code is syntactically invalid: {e}")

        validator = ASTSecurityValidator()
        validator.visit(tree)
