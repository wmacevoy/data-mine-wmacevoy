#!/usr/bin/env python3
"""
meta.py — List available data sources (USGS) from config.json

Usage:
  python meta.py [--format table|json]

Defaults to pretty table.
"""

from __future__ import annotations

import argparse
import json
import os
from typing import Dict

from usgs import SITE_CATALOG


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="List available USGS sources")
    parser.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        help="Output format",
    )
    return parser.parse_args()


def load_sources() -> Dict[str, str]:
    # SITE_CATALOG is already loaded from config with fallback in usgs.py
    return SITE_CATALOG


def print_table(sources: Dict[str, str]) -> None:
    if not sources:
        print("No sources configured.")
        return
    # Simple fixed-width columns
    label_width = max(len(k) for k in sources.keys())
    code_width = max(len(v) for v in sources.values())
    header_label = "Label"
    header_code = "USGS Site Code"
    label_width = max(label_width, len(header_label))
    code_width = max(code_width, len(header_code))
    print(f"{header_label:<{label_width}}  {header_code:<{code_width}}")
    print(f"{'-' * label_width}  {'-' * code_width}")
    for label, code in sources.items():
        print(f"{label:<{label_width}}  {code:<{code_width}}")


def main() -> None:
    args = parse_args()
    sources = load_sources()
    if args.format == "json":
        print(json.dumps({"usgs_sources": sources}, indent=2))
    else:
        print_table(sources)


if __name__ == "__main__":
    main()


