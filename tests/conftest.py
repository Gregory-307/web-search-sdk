"""Pytest configuration and helper utilities for consistent test output."""


def show(title: str, what: str, sent: str, returned: str, status: str = "PASS") -> None:
    """Print a fixed-format block so all tests look the same on stdout."""
    print(f"\n========== {title} ==========\n{what}\n{sent}\n{returned}\nSTATUS : {status}\n\n")
