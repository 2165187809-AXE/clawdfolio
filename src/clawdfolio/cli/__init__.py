"""Command-line interface package for Clawdfolio."""

from __future__ import annotations


def create_parser():  # type: ignore[no-untyped-def]
    """Lazily import parser factory to avoid runpy module warnings."""
    from .main import create_parser as _create_parser

    return _create_parser()


def main(argv: list[str] | None = None) -> int:
    """Lazily import CLI entry point to avoid eager module loading side effects."""
    from .main import main as _main

    return _main(argv)


__all__ = ["main", "create_parser"]
