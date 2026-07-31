#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

HTTP_METHODS = {"get", "put", "post", "delete", "patch", "options", "head", "trace"}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reject removals from the committed Android API surface"
    )
    parser.add_argument("baseline", type=Path)
    parser.add_argument("candidate", type=Path)
    args = parser.parse_args()

    baseline = load(args.baseline)
    candidate = load(args.candidate)
    breaks: list[str] = []

    for path, baseline_path in baseline.get("paths", {}).items():
        candidate_path = candidate.get("paths", {}).get(path)
        if candidate_path is None:
            breaks.append(f"removed path: {path}")
            continue
        for method, operation in baseline_path.items():
            if method not in HTTP_METHODS:
                continue
            candidate_operation = candidate_path.get(method)
            if candidate_operation is None:
                breaks.append(f"removed operation: {method.upper()} {path}")
                continue
            old_responses = operation.get("responses", {})
            new_responses = candidate_operation.get("responses", {})
            for status in old_responses:
                if status not in new_responses:
                    breaks.append(
                        f"removed response {status}: {method.upper()} {path}"
                    )

    old_schemas = baseline.get("components", {}).get("schemas", {})
    new_schemas = candidate.get("components", {}).get("schemas", {})
    for name, old_schema in old_schemas.items():
        new_schema = new_schemas.get(name)
        if new_schema is None:
            breaks.append(f"removed schema: {name}")
            continue
        old_properties = old_schema.get("properties", {})
        new_properties = new_schema.get("properties", {})
        for field in old_properties:
            if field not in new_properties:
                breaks.append(f"removed field: {name}.{field}")
        newly_required = set(new_schema.get("required", [])) - set(
            old_schema.get("required", [])
        )
        for field in sorted(newly_required):
            breaks.append(f"new required field: {name}.{field}")

    if breaks:
        print("Breaking OpenAPI changes detected:")
        for item in breaks:
            print(f"- {item}")
        raise SystemExit(1)

    print("No removed paths, operations, responses, schemas, fields, or new required fields.")


if __name__ == "__main__":
    main()
