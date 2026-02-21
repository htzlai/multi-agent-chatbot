#
# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""ChatAgent implementation for LLM-powered conversational AI with tool calling."""

import asyncio
import contextlib
import json
from typing import AsyncIterator, List, Dict, Any, TypedDict, Optional, Callable, Awaitable

import httpx
from langchain_core.messages import HumanMessage, AIMessage, AnyMessage, SystemMessage, ToolMessage, ToolCall
from langchain_core.utils.function_calling import convert_to_openai_tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from openai import AsyncOpenAI

from client import MCPClient
from logger import logger
from prompts import Prompts
from postgres_storage import PostgreSQLConversationStorage
from utils import convert_langgraph_messages_to_openai
from langfuse_client import get_langfuse_client, flush_langfuse


memory = MemorySaver()
SENTINEL = object()
StreamCallback = Callable[[Dict[str, Any]], Awaitable[None]]


class State(TypedDict, total=False):
    iterations: int
    messages: List[AnyMessage]
    chat_id: Optional[str]
    image_data: Optional[str]


class ChatAgent:
    """Main conversational agent with tool calling and agent delegation capabilities.
    
    This agent orchestrates conversation flow using a LangGraph state machine that can:
    - Generate responses using LLMs
    - Execute tool calls (including MCP tools)
    - Handle image processing
    - Manage conversation history via Redis
    """

    def __init__(self, vector_store, config_manager, postgres_storage: PostgreSQLConversationStorage):
        """Initialize the chat agent.
        
        Args:
            vector_store: VectorStore instance for document retrieval
            config_manager: ConfigManager for reading configuration
            postgres_storage: PostgreSQL storage for conversation persistence
        """
        self.vector_store = vector_store
        self.config_manager = config_manager
        self.conversation_store = postgres_storage
        self.current_model = None
        
        self.current_model = None
        self.max_iterations = 3
        
        self.mcp_client = None
        self.openai_tools = None
        self.tools_by_name = None
        self.system_prompt = None
        
        self.graph = self._build_graph()
        self.stream_callback = None
        self.last_state = None

        # Langfuse observability
        self.langfuse = get_langfuse_client()
        self._current_trace = None

    @classmethod
    async def create(cls, vector_store, config_manager, postgres_storage: PostgreSQLConversationStorage):
        """
        Asynchronously creates and initializes a ChatAgent instance.
        
        This factory method ensures that all async setup, like loading tools,
        is completed before the agent is ready to be used.
        """
        agent = cls(vector_store, config_manager, postgres_storage)
        await agent.init_tools()
        
        available_tools = list(agent.tools_by_name.values()) if agent.tools_by_name else []
        template_vars = {
            "tools": "\n".join([f"- {tool.name}: {tool.description}" for tool in available_tools]) if available_tools else "No tools available",
        }
        agent.system_prompt = Prompts.get_template("supervisor_agent").render(template_vars)
        
        logger.debug(f"Agent initialized with {len(available_tools)} tools.")
        agent.set_current_model(config_manager.get_selected_model())
        return agent

    async def init_tools(self) -> None:
        """Initialize MCP client and tools with retry logic.
        
        Sets up the MCP client, retrieves available tools, converts them to OpenAI format,
        and initializes specialized agents like the coding agent.
        """
        self.mcp_client = await MCPClient().init()
        
        base_delay, max_retries = 0.1, 10
        mcp_tools = []
        
        for attempt in range(max_retries):
            try:
                mcp_tools = await self.mcp_client.get_tools()
                break
            except Exception as e:
                logger.warning(f"MCP tools initialization attempt {attempt + 1} failed: {e}")
                if attempt == max_retries - 1:
                    logger.error(f"MCP servers not ready after {max_retries} attempts, continuing without MCP tools")
                    mcp_tools = []
                    break
                wait_time = base_delay * (2 ** attempt)
                await asyncio.sleep(wait_time)
                logger.info(f"MCP servers not ready, retrying in {wait_time}s (attempt {attempt + 1}/{max_retries})")
        
        self.tools_by_name = {tool.name: tool for tool in mcp_tools}
        logger.debug(f"Loaded {len(mcp_tools)} MCP tools: {list(self.tools_by_name.keys())}")
        
        if mcp_tools:
            mcp_tools_openai = [convert_to_openai_tool(tool) for tool in mcp_tools]
            logger.debug(f"MCP tools converted to OpenAI format: {mcp_tools_openai}")
            
            self.openai_tools = [
                {"type": "function", "function": tool['function']} 
                for tool in mcp_tools_openai
            ]
            logger.debug(f"Final OpenAI tools format: {self.openai_tools}")
        else:
            self.openai_tools = []
            logger.warning("No MCP tools available - agent will run with limited functionality")

    def set_current_model(self, model_name: str) -> None:
        """Set the current model for completions.
        
        Args:
            model_name: Name of the model to use
            
        Raises:
            ValueError: If the model is not available
        """
        available_models = self.config_manager.get_available_models()

        try:
            if model_name in available_models:
                self.current_model = model_name
                logger.info(f"Switched to model: {model_name}")
                # 创建支持请求取消的自定义 httpx 客户端
                # 使用较长的超时以支持大模型推理，同时允许主动取消
                self._http_client = httpx.AsyncClient(
                    timeout=httpx.Timeout(
                        connect=30.0,      # 连接超时 30 秒
                        read=300.0,        # 读取超时 5 分钟（大模型可能需要较长时间）
                        write=30.0,        # 写入超时 30 秒
                        pool=30.0          # 连接池超时 30 秒
                    ),
                    limits=httpx.Limits(
                        max_connections=10,
                        max_keepalive_connections=5
                    )
                )
                self.model_client = AsyncOpenAI(
                    base_url=f"http://{self.current_model}:8000/v1",
                    api_key="api_key",
                    http_client=self._http_client  # 使用自定义客户端
                )
            else:
                raise ValueError(f"Model {model_name} is not available. Available models: {available_models}")
        except Exception as e:
            logger.error(f"Error setting current model: {e}")
            raise ValueError(f"Model {model_name} is not available. Available models: {available_models}")

    def should_continue(self, state: State) -> str:
        """Determine whether to continue the tool calling loop.
        
        Args:
            state: Current graph state
            
        Returns:
            "end" if no more tool calls or max iterations reached, "continue" otherwise
        """
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
        """Execute tools from the last AI message's tool calls.
        
        Args:
            state: Current graph state
            
        Returns:
            Updated state with tool results and incremented iteration count
        """
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
        """Generate AI response using the current model.
        
        Args:
            state: Current graph state
            
        Returns:
            Updated state with new AI message
        """
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
            max_tokens=16384,  # 增加输出限制，支持更长内容（8000+字）
            **tool_params
        )

        # 传递 stop_event 给流处理方法
        llm_output_buffer, tool_calls_buffer = await self._stream_response(
            stream, 
            self.stream_callback,
            stop_event=getattr(self, '_stop_event', None)
        )
        tool_calls = self._format_tool_calls(tool_calls_buffer)
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

        # Langfuse: end generation with token counts (local LLMs don't return usage)
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

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state machine for conversation flow.
        
        Returns:
            Compiled StateGraph with nodes and conditional edges
        """
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

    def _format_tool_calls(self, tool_calls_buffer: Dict[int, Dict[str, str]]) -> List[ToolCall]:
        """Parse streamed tool call buffer into ToolCall objects.
        
        Args:
            tool_calls_buffer: Buffer of streamed tool call data
            
        Returns:
            List of formatted ToolCall objects
        """
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

    async def _stream_response(self, stream, stream_callback: StreamCallback, stop_event: asyncio.Event = None) -> tuple[List[str], Dict[int, Dict[str, str]]]:
        """Process streaming LLM response and extract content and tool calls.
        
        Args:
            stream: Async stream from LLM
            stream_callback: Callback for streaming events
            stop_event: Optional event to signal stream interruption
            
        Returns:
            Tuple of (content_buffer, tool_calls_buffer)
        """
        llm_output_buffer = []
        tool_calls_buffer = {}
        saw_tool_finish = False

        try:
            async for chunk in stream:
                # 检查是否需要中断生成
                if stop_event and stop_event.is_set():
                    logger.info("Stream interrupted by stop_event, closing connection")
                    # 主动关闭底层 HTTP 连接
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
        """Close the underlying HTTP connection of a stream.
        
        Args:
            stream: The stream object to close
        """
        try:
            # OpenAI SDK 的流对象内部有 _client_response 属性
            if hasattr(stream, '_client_response'):
                response = stream._client_response
                if hasattr(response, 'aclose'):
                    await response.aclose()
                    logger.debug("Closed stream client response")
            # 尝试关闭 httpx Response
            if hasattr(stream, 'response'):
                response = stream.response
                if hasattr(response, 'aclose'):
                    await response.aclose()
                    logger.debug("Closed stream response")
            # 尝试关闭 stream 本身
            if hasattr(stream, 'close'):
                if asyncio.iscoroutinefunction(stream.close):
                    await stream.close()
                else:
                    stream.close()
                logger.debug("Closed stream directly")
        except Exception as e:
            logger.warning(f"Error closing stream connection: {e}")

    async def query(self, query_text: str, chat_id: str, image_data: str = None, stop_event=None) -> AsyncIterator[Dict[str, Any]]:
        """Process user query and stream response tokens.
        
        Args:
            query_text: User's input text
            chat_id: Unique chat identifier
            stop_event: Optional event to signal generation interruption
            
        Yields:
            Streaming events and tokens
        """
        logger.debug({
            "message": "GRAPH: STARTING EXECUTION",
            "chat_id": chat_id,
            "query": query_text[:100] + "..." if len(query_text) > 100 else query_text,
            "graph_flow": "START → generate → should_continue → action → generate → END"
        })

        # 存储 stop_event 供 generate 方法使用
        self._stop_event = stop_event

        config = {"configurable": {"thread_id": chat_id}}

        # Langfuse: create trace for this conversation
        if self.langfuse:
            try:
                self._current_trace = self.langfuse.trace(
                    name="chat",
                    metadata={"chat_id": chat_id}
                )
            except Exception as e:
                logger.debug(f"Langfuse trace creation failed: {e}")
                self._current_trace = None

        try:
            existing_messages = await self.conversation_store.get_messages(chat_id, limit=1)
            
            base_system_prompt = self.system_prompt
            if image_data:
                image_context = "\n\nIMAGE CONTEXT: The user has uploaded an image with their message. You MUST use the explain_image tool to analyze it."
                system_prompt_with_image = base_system_prompt + image_context
                messages_to_process = [SystemMessage(content=system_prompt_with_image)]
            else:
                messages_to_process = [SystemMessage(content=base_system_prompt)]

            if existing_messages:
                for msg in existing_messages:
                    if not isinstance(msg, SystemMessage):
                        messages_to_process.append(msg)

            messages_to_process.append(HumanMessage(content=query_text))

            config_obj = self.config_manager.read_config()

            initial_state = {
                "iterations": 0,
                "chat_id": chat_id,
                "messages": messages_to_process,
                "image_data": image_data if image_data else None,
                "process_image_used": False
            }
            

            model_name = self.config_manager.get_selected_model()
            if self.current_model != model_name:
                self.set_current_model(model_name)

            logger.debug({
                "message": "GRAPH: LAUNCHING EXECUTION",
                "chat_id": chat_id,
                "initial_state": {
                    "iterations": initial_state["iterations"],
                    "message_count": len(initial_state["messages"]),
                }
            })

            self.last_state = None
            token_q: asyncio.Queue[Any] = asyncio.Queue()
            self.stream_callback = lambda event: self._queue_writer(event, token_q)
            runner = asyncio.create_task(self._run_graph(initial_state, config, chat_id, token_q))

            try:
                while True:
                    # 检查是否需要停止生成
                    if stop_event and stop_event.is_set():
                        logger.info(f"Stop event detected, cancelling runner for chat {chat_id}")
                        runner.cancel()
                        try:
                            await runner
                        except asyncio.CancelledError:
                            pass
                        yield {"type": "stopped", "message": "Generation stopped"}
                        break
                    
                    # 使用 wait_for 来同时等待队列和检查 stop_event
                    try:
                        item = await asyncio.wait_for(token_q.get(), timeout=0.1)
                    except asyncio.TimeoutError:
                        continue
                        
                    if item is SENTINEL:
                        break
                    yield item
            except asyncio.CancelledError:
                logger.info(f"Query cancelled for chat {chat_id}")
                runner.cancel()
                try:
                    await runner
                except asyncio.CancelledError:
                    pass
                raise
            except Exception as stream_error:
                logger.error({"message": "Error in streaming", "error": str(stream_error)}, exc_info=True)
            finally:
                # 清理 stop_event 引用
                self._stop_event = None
                with contextlib.suppress(asyncio.CancelledError):
                    await runner

                logger.debug({
                    "message": "GRAPH: EXECUTION COMPLETED",
                    "chat_id": chat_id,
                    "final_iterations": self.last_state.get("iterations", 0) if self.last_state else 0
                })

        except Exception as e:
            logger.error({"message": "GRAPH: EXECUTION FAILED", "error": str(e), "chat_id": chat_id}, exc_info=True)
            yield {"type": "error", "data": f"Error performing query: {str(e)}"}


    async def _queue_writer(self, event: Dict[str, Any], token_q: asyncio.Queue) -> None:
        """Write events to the streaming queue.
        
        Args:
            event: Event data to queue
            token_q: Queue for streaming events
        """
        await token_q.put(event)

    async def _run_graph(self, initial_state: Dict[str, Any], config: Dict[str, Any], chat_id: str, token_q: asyncio.Queue) -> None:
        """Run the graph execution in background task.
        
        Args:
            initial_state: Starting state for graph
            config: LangGraph configuration
            chat_id: Chat identifier
            token_q: Queue for streaming events
        """
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
                # Langfuse: flush pending events
                if self.langfuse:
                    flush_langfuse()
