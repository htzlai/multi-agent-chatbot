# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""ChatAgent — main entry point assembling graph, streaming, and observability mixins."""

import asyncio
import contextlib
import os
from typing import Any, AsyncIterator, Dict

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.utils.function_calling import convert_to_openai_tool
from openai import AsyncOpenAI

from client import MCPClient
from logger import logger
from prompts import Prompts
from postgres_storage import PostgreSQLConversationStorage
from agent.graph import _GraphMixin
from agent.streaming import SENTINEL, _StreamingMixin
from agent.observability import get_langfuse_client

# ============================================================
# Third-party API configuration
# ============================================================

LLM_API_TYPE = os.getenv("LLM_API_TYPE", "local")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "http://gpt-oss-120b:8000/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "api_key")
EXTERNAL_MODELS = os.getenv("EXTERNAL_MODELS", "").split(",") if os.getenv("EXTERNAL_MODELS") else []
EXTERNAL_MODEL_NAME = os.getenv("EXTERNAL_MODEL_NAME", "llama3")


class ChatAgent(_GraphMixin, _StreamingMixin):
    """Main conversational agent with tool calling and agent delegation capabilities.

    This agent orchestrates conversation flow using a LangGraph state machine that can:
    - Generate responses using LLMs
    - Execute tool calls (including MCP tools)
    - Handle image processing
    - Manage conversation history via PostgreSQL
    """

    def __init__(self, vector_store, config_manager, postgres_storage: PostgreSQLConversationStorage):
        self.vector_store = vector_store
        self.config_manager = config_manager
        self.conversation_store = postgres_storage
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
        """Async factory — creates and initializes a ChatAgent with MCP tools loaded."""
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
        """Initialize MCP client and tools with retry logic."""
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

    def _create_model_client(self, base_url: str, api_key: str) -> AsyncOpenAI:
        """Create an AsyncOpenAI client with shared httpx configuration."""
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(
                connect=30.0,
                read=300.0,
                write=30.0,
                pool=30.0,
            ),
            limits=httpx.Limits(
                max_connections=10,
                max_keepalive_connections=5,
            ),
        )
        return AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            http_client=self._http_client,
        )

    def set_current_model(self, model_name: str) -> None:
        """Set the current model for completions."""
        available_models = self.config_manager.get_available_models()

        if LLM_API_TYPE == "openai":
            if EXTERNAL_MODELS:
                available_models = EXTERNAL_MODELS

            try:
                if model_name in available_models or model_name == EXTERNAL_MODEL_NAME:
                    self.current_model = model_name if model_name in available_models else EXTERNAL_MODEL_NAME
                    logger.info(f"Switching to external model: {self.current_model} (API: {LLM_BASE_URL})")
                    self.model_client = self._create_model_client(LLM_BASE_URL, LLM_API_KEY)
                else:
                    raise ValueError(f"Model {model_name} is not available. Available models: {available_models}")
            except Exception as e:
                logger.error(f"Error setting current model: {e}")
                raise ValueError(f"Model {model_name} is not available. Available models: {available_models}")
        else:
            try:
                if model_name in available_models:
                    self.current_model = model_name
                    logger.info(f"Switched to model: {model_name}")
                    self.model_client = self._create_model_client(
                        f"http://{self.current_model}:8000/v1", "api_key"
                    )
                else:
                    raise ValueError(f"Model {model_name} is not available. Available models: {available_models}")
            except Exception as e:
                logger.error(f"Error setting current model: {e}")
                raise ValueError(f"Model {model_name} is not available. Available models: {available_models}")

    async def query(self, query_text: str, chat_id: str, image_data: str = None, stop_event=None) -> AsyncIterator[Dict[str, Any]]:
        """Process user query and stream response tokens."""
        logger.debug({
            "message": "GRAPH: STARTING EXECUTION",
            "chat_id": chat_id,
            "query": query_text[:100] + "..." if len(query_text) > 100 else query_text,
            "graph_flow": "START → generate → should_continue → action → generate → END"
        })

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
                    if stop_event and stop_event.is_set():
                        logger.info(f"Stop event detected, cancelling runner for chat {chat_id}")
                        runner.cancel()
                        try:
                            await runner
                        except asyncio.CancelledError:
                            pass
                        yield {"type": "stopped", "message": "Generation stopped"}
                        break

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
