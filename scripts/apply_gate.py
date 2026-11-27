#!/usr/bin/env python3
"""Compatibility entry point for the Member 2 release gate CLI."""
from eval_bootstrap import ROOT  # noqa: F401
from ragops.evalsuite.gate_cli import entrypoint

if __name__ == "__main__":
    raise SystemExit(entrypoint())
