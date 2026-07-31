#!/bin/sh
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
output_dir="$repo_dir/generated/android-client"

docker run --rm \
  -v "$repo_dir:/workspace:ro" \
  -v "$output_dir:/output" \
  openapitools/openapi-generator-cli:v7.14.0 generate \
  -i /workspace/docs/api/openapi-v1.json \
  -g kotlin \
  -o /output \
  --additional-properties=library=jvm-retrofit2,serializationLibrary=kotlinx_serialization,packageName=com.bessa.securo.api

echo "Generated Kotlin client: $output_dir"
