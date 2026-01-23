"""JSON output validation and correction"""
from __future__ import annotations

import json
import re
from typing import Type, TypeVar

from pydantic import BaseModel, ValidationError


_JSON_BLOCK_RE = re.compile(r"\{.*\}", re.DOTALL)

T = TypeVar('T', bound=BaseModel)


def extract_json(text: str) -> dict:
    match = _JSON_BLOCK_RE.search(text)
    if not match:
        raise ValueError("No JSON object found in LLM output")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as e:
        # Show the extracted block that failed to parse for easier debugging
        print("\n=== RAW JSON CANDIDATE (extract failure) ===")
        print(match.group(0))
        print("=== END RAW JSON CANDIDATE ===\n")
        raise


def parse_with_schema(text: str, schema: Type[T]) -> T:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        # Show the raw model output to help debug malformed JSON or truncation
        print("\n=== RAW LLM TEXT (parse failure) ===")
        print(text)
        print("=== END RAW TEXT ===\n")
        data = extract_json(text)

    try:
        return schema.model_validate(data)
    except ValidationError as e:
        print(f"\n=== LLM OUTPUT ===\n{text}\n")
        print(f"\n=== EXTRACTED DATA ===\n{json.dumps(data, indent=2)}\n")
        raise ValueError(f"Schema validation failed: {e}") from e
