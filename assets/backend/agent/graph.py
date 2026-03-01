# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""LangGraph state machine — graph construction, generate node, tool node, and control flow."""

import json
from typing import Any, Dict, List, Optional, TypedDict

from langchain_core.messages import AIMessage, AnyMessage, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from logger import logger
from agent.formatting import convert_langgraph_messages_to_openai, format_tool_calls

memory = MemorySaver()


class State(TypedDict, total=False):
    iterations: int
    messages: List[AnyMessage]
    chat_id: Optional[str]
    image_data: Optional[str]


class _GraphMixin:
    """Mixin providing LangGraph state machine methods for ChatAgent."""

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state machine for conversation flow."""
        workflow = StateGraph(State)

        workflow.add_node("generate", self.generate)
        workflow.add_node("action", self.tool_node)
        workflow.add_edge(START, "generate")
        workflow.add_conditional_edges(
            "generate",
            self.should_continue,
            {
                "continue": "action",
                "end": END,
            },
        )
        workflow.add_edge("action", "generate")

        return workflow.compile(checkpointer=memory)

    def should_continue(self, state: State) -> str:
        """Determine whether to continue the tool calling loop."""
        messages = state.get("messages", [])
        if not messages:
            return "end"

        last_message = messages[-1]
        iterations = state.get("iterations", 0)
        has_tool_calls = bool(last_message.tool_calls) if hasattr(last_message, 'tool_calls') else False

        logger.debug({
            "message": "GRAPH: should_continue decision",
            "chat_id": state.get("chat_id"),
            "iterations": iterations,
            "max_iterations": self.max_iterations,
            "has_tool_calls": has_tool_calls,
            "tool_calls_count": len(last_message.tool_calls) if has_tool_calls else 0
        })

        if iterations >= self.max_iterations:
            logger.debug({
                "message": "GRAPH: should_continue → END (max iterations reached)",
                "chat_id": state.get("chat_id"),
                "final_message_preview": str(last_message)[:100] + "..." if len(str(last_message)) > 100 else str(last_message)
            })
            return "end"

        if not has_tool_calls:
            logger.debug({"message": "GRAPH: should_continue → END (no tool calls)", "chat_id": state.get("chat_id")})
            return "end"

        logger.debug({"message": "GRAPH: should_continue → CONTINUE (has tool calls)", "chat_id": state.get("chat_id")})
        return "continue"

    async def tool_node(self, state: State) -> Dict[str, Any]:
        """Execute tools from the last AI message's tool calls."""
        logger.debug({
            "message": "GRAPH: ENTERING NODE - action/tool_node",
            "chat_id": state.get("chat_id"),
            "iterations": state.get("iterations", 0)
        })
        await self.stream_callback({'type': 'node_start', 'data': 'tool_node'})

        outputs = []
        messages = state.get("messages", [])
        last_message = messages[-1]
        for i, tool_call in enumerate(last_message.tool_calls):
            logger.debug(f'Executing tool {i+1}/{len(last_message.tool_calls)}: {tool_call["name"]} with args: {tool_call["args"]}')
            await self.stream_callback({'type': 'tool_start', 'data': tool_call["name"]})

            try:
                if tool_call["name"] == "explain_image" and state.get("image_data"):
                    tool_args = tool_call["args"].copy()
                    tool_args["image"] = state["image_data"]
                    logger.info(f'Executing tool {tool_call["name"]} with args: {tool_args}')
                    tool_result = await self.tools_by_name[tool_call["name"]].ainvoke(tool_args)
                    state["process_image_used"] = True
                else:
                    tool_result = await self.tools_by_name[tool_call["name"]].ainvoke(tool_call["args"])
                if "code" in tool_call["name"]:
                    content = str(tool_result)
                elif isinstance(tool_result, str):
                    content = tool_result
                else:
                    content = json.dumps(tool_result)
            except Exception as e:
                logger.error(f'Error executing tool {tool_call["name"]}: {str(e)}', exc_info=True)
                content = f"Error executing tool '{tool_call['name']}': {str(e)}"

            await self.stream_callback({'type': 'tool_end', 'data': tool_call["name"]})

            outputs.append(
                ToolMessage(
                    content=content,
                    name=tool_call["name"],
                    tool_call_id=tool_call["id"],
                )
            )

        state["iterations"] = state.get("iterations", 0) + 1

        logger.debug({
            "message": "GRAPH: EXITING NODE - action/tool_node",
            "chat_id": state.get("chat_id"),
            "iterations": state.get("iterations"),
            "tools_executed": len(outputs),
            "next_step": "→ returning to generate"
        })
        await self.stream_callback({'type': 'node_end', 'data': 'tool_node'})
        return {"messages": messages + outputs, "iterations": state.get("iterations", 0) + 1}

    async def generate(self, state: State) -> Dict[str, Any]:
        """Generate AI response using the current model."""
        messages = convert_langgraph_messages_to_openai(state.get("messages", []))
        logger.debug({
            "message": "GRAPH: ENTERING NODE - generate",
            "chat_id": state.get("chat_id"),
            "iterations": state.get("iterations", 0),
            "current_model": self.current_model,
            "message_count": len(state.get("messages", []))
        })
        await self.stream_callback({'type': 'node_start', 'data': 'generate'})

        # Langfuse: create generation for LLM call
        generation = None
        if self.langfuse and self._current_trace:
            try:
                generation = self._current_trace.generation(
                    name="llm",
                    model=self.current_model,
                    input=messages,
                    metadata={"chat_id": state.get("chat_id"), "iterations": state.get("iterations", 0)},
                )
            except Exception as e:
                logger.debug(f"Langfuse generation creation failed: {e}")

        supports_tools = self.current_model in {"gpt-oss-20b", "gpt-oss-120b"}
        has_tools = supports_tools and self.openai_tools and len(self.openai_tools) > 0

        logger.debug({
            "message": "Tool calling debug info",
            "chat_id": state.get("chat_id"),
            "current_model": self.current_model,
            "supports_tools": supports_tools,
            "openai_tools_count": len(self.openai_tools) if self.openai_tools else 0,
            "openai_tools": self.openai_tools,
            "has_tools": has_tools
        })

        tool_params = {}
        if has_tools:
            tool_params = {
                "tools": self.openai_tools,
                "tool_choice": "auto"
            }

        stream = await self.model_client.chat.completions.create(
            model=self.current_model,
            messages=messages,
            temperature=0,
            top_p=1,
            stream=True,
            max_tokens=16384,
            **tool_params
        )

        llm_output_buffer, tool_calls_buffer = await self._stream_response(
            stream,
            self.stream_callback,
            stop_event=getattr(self, '_stop_event', None)
        )
        tool_calls = format_tool_calls(tool_calls_buffer)
        raw_output = "".join(llm_output_buffer)

        logger.debug({
            "message": "Tool call generation results",
            "chat_id": state.get("chat_id"),
            "tool_calls_buffer": tool_calls_buffer,
            "formatted_tool_calls": tool_calls,
            "tool_calls_count": len(tool_calls),
            "raw_output_length": len(raw_output),
            "raw_output": raw_output[:200] + "..." if len(raw_output) > 200 else raw_output
        })

        response = AIMessage(
            content=raw_output,
            **({"tool_calls": tool_calls} if tool_calls else {})
        )

        logger.debug({
            "message": "GRAPH: EXITING NODE - generate",
            "chat_id": state.get("chat_id"),
            "iterations": state.get("iterations", 0),
            "response_length": len(response.content) if response.content else 0,
            "tool_calls_generated": len(tool_calls),
            "tool_calls_names": [tc["name"] for tc in tool_calls] if tool_calls else [],
            "next_step": "→ should_continue decision"
        })
        await self.stream_callback({'type': 'node_end', 'data': 'generate'})

        # Langfuse: end generation with token counts
        if generation:
            try:
                import tiktoken
                enc = tiktoken.get_encoding("cl100k_base")
                prompt_tokens = len(enc.encode(str(messages)))
                completion_tokens = len(enc.encode(raw_output))
                generation.end(
                    output=raw_output,
                    usage={
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "total_tokens": prompt_tokens + completion_tokens
                    }
                )
            except Exception as e:
                logger.debug(f"Langfuse generation end failed: {e}")
                try:
                    generation.end(output=raw_output)
                except:
                    pass

        return {"messages": state.get("messages", []) + [response]}
