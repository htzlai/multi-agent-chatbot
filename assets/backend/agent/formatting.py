# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Pure functions for message format conversion between LangGraph and OpenAI."""

import json
from typing import Any, Dict, List

from langchain_core.messages import AIMessage, HumanMessage, ToolCall, ToolMessage


def convert_langgraph_messages_to_openai(messages: list) -> list[dict[str, Any]]:
    """Convert LangGraph message objects to OpenAI API format."""
    openai_messages = []
    for msg in messages:
        if isinstance(msg, HumanMessage):
            openai_messages.append({"role": "user", "content": msg.content})
        elif isinstance(msg, AIMessage):
            openai_msg = {"role": "assistant", "content": msg.content or ""}
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                openai_msg["tool_calls"] = [
                    {
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": json.dumps(tc["args"])},
                    }
                    for tc in msg.tool_calls
                ]
            openai_messages.append(openai_msg)
        elif isinstance(msg, ToolMessage):
            openai_messages.append({
                "role": "tool",
                "content": msg.content,
                "tool_call_id": msg.tool_call_id,
            })
    return openai_messages


def format_tool_calls(tool_calls_buffer: Dict[int, Dict[str, str]]) -> List[ToolCall]:
    """Parse streamed tool call buffer into ToolCall objects."""
    if not tool_calls_buffer:
        return []

    tool_calls = []
    for i in sorted(tool_calls_buffer):
        item = tool_calls_buffer[i]
        try:
            parsed_args = json.loads(item["arguments"] or "{}")
        except json.JSONDecodeError:
            parsed_args = {}

        tool_calls.append(
            ToolCall(
                name=item["name"],
                args=parsed_args,
                id=item["id"] or f"call_{i}",
            )
        )
    return tool_calls
