"""Shared API models."""
from typing import Any


class ApiResponse:
    """Standard API response envelope."""

    @staticmethod
    def ok(data: Any = None, message: str = "") -> dict:
        return {"success": True, "data": data, "message": message}

    @staticmethod
    def error(message: str, code: str = "ERROR") -> dict:
        return {"success": False, "error": message, "code": code}
