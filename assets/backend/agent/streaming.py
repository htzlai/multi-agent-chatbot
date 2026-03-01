# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Streaming support — queue-based async token delivery and stream lifecycle."""

import asyncio
from typing import Any, Awaitable, Callable, Dict, List

from logger import logger
from agent.observability import flush_langfuse

SENTINEL = object()
StreamCallback = Callable[[Dict[str, Any]], Awaitable[None]]


class _StreamingMixin:
    """Mixin providing streaming methods for ChatAgent."""

    async def _stream_response(self, stream, stream_callback: StreamCallback, stop_event: asyncio.Event = None) -> tuple[List[str], Dict[int, Dict[str, str]]]:
        """Process streaming LLM response and extract content and tool calls."""
        llm_output_buffer = []
        tool_calls_buffer = {}
        saw_tool_finish = False

        try:
            async for chunk in stream:
                if stop_event and stop_event.is_set():
                    logger.info("Stream interrupted by stop_event, closing connection")
                    await self._close_stream_connection(stream)
                    break

                for choice in getattr(chunk, "choices", []) or []:
                    delta = getattr(choice, "delta", None)
                    if not delta:
                        continue

                    content = getattr(delta, "content", None)
                    if content:
                        await stream_callback({"type": "token", "data": content})
                        llm_output_buffer.append(content)
                    for tc in getattr(delta, "tool_calls", []) or []:
                        idx = getattr(tc, "index", None)
                        if idx is None:
                            idx = 0 if not tool_calls_buffer else max(tool_calls_buffer) + 1
                        entry = tool_calls_buffer.setdefault(idx, {"id": None, "name": None, "arguments": ""})

                        if getattr(tc, "id", None):
                            entry["id"] = tc.id

                        fn = getattr(tc, "function", None)
                        if fn:
                            if getattr(fn, "name", None):
                                entry["name"] = fn.name
                            if getattr(fn, "arguments", None):
                                entry["arguments"] += fn.arguments

                    finish_reason = getattr(choice, "finish_reason", None)
                    if finish_reason == "tool_calls":
                        saw_tool_finish = True
                        break

                if saw_tool_finish:
                    break

        except asyncio.CancelledError:
            logger.info("Stream cancelled by asyncio, cleaning up")
            await self._close_stream_connection(stream)
            raise
        except Exception as e:
            logger.error(f"Error in stream processing: {e}", exc_info=True)
            raise

        return llm_output_buffer, tool_calls_buffer

    async def _close_stream_connection(self, stream) -> None:
        """Close the underlying HTTP connection of a stream."""
        try:
            if hasattr(stream, '_client_response'):
                response = stream._client_response
                if hasattr(response, 'aclose'):
                    await response.aclose()
                    logger.debug("Closed stream client response")
            if hasattr(stream, 'response'):
                response = stream.response
                if hasattr(response, 'aclose'):
                    await response.aclose()
                    logger.debug("Closed stream response")
            if hasattr(stream, 'close'):
                if asyncio.iscoroutinefunction(stream.close):
                    await stream.close()
                else:
                    stream.close()
                logger.debug("Closed stream directly")
        except Exception as e:
            logger.warning(f"Error closing stream connection: {e}")

    async def _queue_writer(self, event: Dict[str, Any], token_q: asyncio.Queue) -> None:
        """Write events to the streaming queue."""
        await token_q.put(event)

    async def _run_graph(self, initial_state: Dict[str, Any], config: Dict[str, Any], chat_id: str, token_q: asyncio.Queue) -> None:
        """Run the graph execution in background task."""
        try:
            async for final_state in self.graph.astream(
                initial_state,
                config=config,
                stream_mode="values",
                stream_writer=lambda event: self._queue_writer(event, token_q)
            ):
                self.last_state = final_state
        finally:
            try:
                if self.last_state and self.last_state.get("messages"):
                    final_msg = self.last_state["messages"][-1]
                    try:
                        logger.debug(f'Saving messages to conversation store for chat: {chat_id}')
                        await self.conversation_store.save_messages(chat_id, self.last_state["messages"])
                    except Exception as save_err:
                        logger.warning({"message": "Failed to persist conversation", "chat_id": chat_id, "error": str(save_err)})

                    content = getattr(final_msg, "content", None)
                    if content:
                        await token_q.put(content)
            finally:
                await token_q.put(SENTINEL)
                if self.langfuse:
                    flush_langfuse()
