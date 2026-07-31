#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from app.main import app


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Securo's versioned OpenAPI contract")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
