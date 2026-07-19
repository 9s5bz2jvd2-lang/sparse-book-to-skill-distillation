#!/usr/bin/env python3
"""Compatibility alias for scripts/query.py; runtime experts must come from a built v2 registry."""

from query import main


if __name__ == "__main__":
    raise SystemExit(main())
