from __future__ import annotations
from collections import defaultdict
from enum import Enum
from typing import Dict
from .schemas.base import ErrorResponse


# Automatically builds the responses(docs) for each endpoint based on their error enums
def build_responses(*members: Enum, media_type: str = "application/json") -> Dict[int, dict]:

    # Groups based status code
    # Some endpoint error enums share the same status code for two or more different items
    # If we don't group them they just override each other when building the responses
    grouped: Dict[int, list] = defaultdict(list)
    for member in members:
        grouped[member.value.http_status].append(member)

    responses: Dict[int, dict] = {}
    for status_code, group in grouped.items():
        if len(group) == 1:
            m = group[0]
            content = {
                "example": {
                    "success": False,
                    "message": m.value.message,
                    "err_code": m.value.code,
                }
            }
            description = m.value.message
        else:
            content = {
                "examples": {
                    f"{type(m).__name__}.{m.name}": {
                        "summary": m.value.message,
                        "value": {
                            "success": False,
                            "message": m.value.message,
                            "err_code": m.value.code,
                        },
                    }
                    for m in group
                }
            }
            description = "Multiple possible causes -- see examples."

        responses[status_code] = {
            "model": ErrorResponse,
            "description": description,
            "content": {media_type: content},
        }

    return responses
