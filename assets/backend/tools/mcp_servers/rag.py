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

"""RAG MCP Server for Document Search and Question Answering.

This module implements an MCP server that provides document search capabilities using
a simple retrieval-augmented generation (RAG) pipeline. The server exposes a 
search_documents tool that retrieves relevant document chunks and generates answers.

The simplified RAG workflow consists of:
    - Document retrieval from a vector store
    - Answer generation using retrieved context
"""
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Annotated, Dict, List, Optional, Sequence, TypedDict

from langchain_core.documents import Document
from langchain_core.messages import AnyMessage, HumanMessage, AIMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph, add_messages
from mcp.server.fastmcp import FastMCP
from openai import AsyncOpenAI
from pypdf import PdfReader

project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))

from config import ConfigManager
from services.vector_store_service import VectorStore, create_vector_store_with_config


logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(name)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class RAGState(TypedDict, total=False):
    """Type definition for the simplified RAG agent state.

    Attributes:
        question: The user's question to be answered.
        messages: Conversation history with automatic message aggregation.
        context: Retrieved documents from the local vector store.
        sources: Optional list of source filters for retrieval.
        scores: Optional list of similarity scores for retrieved documents.
    """
    question: str
    messages: Annotated[Sequence[AnyMessage], add_messages]
    context: Optional[List[Document]]
    sources: Optional[List[str]]
    scores: Optional[List[float]]


class RAGAgent:
    """Simplified RAG Agent for fast document search and answer generation.
    
    This agent manages a simple two-step pipeline:
    1. Retrieve documents from the local vector store.
    2. Generate an answer using the retrieved context.
    """
    
    def __init__(self):
        """Initialize the RAG agent with model client, configuration, and graph."""
        config_path = self._get_config_path()
        self.config_manager = ConfigManager(config_path)
        self.vector_store = create_vector_store_with_config(self.config_manager)
        self.model_name = self.config_manager.get_selected_model()
        self.model_client = AsyncOpenAI(
            base_url=f"http://{self.model_name}:8000/v1",
            api_key="api_key"
        )

        self.generation_prompt = self._get_generation_prompt()
        

        self.graph = self._build_graph()

    def _get_config_path(self):
        """Get the configuration file path and validate its existence."""
        config_path = os.path.join(os.path.dirname(__file__), "../../config.json")
        if not os.path.exists(config_path):
            logger.error("ERROR: config.json not found")
        return config_path

    def _get_generation_prompt(self) -> str:
        """Get the system prompt template for the generation node."""
        return """You are an assistant for question-answering tasks. 
        Use the following pieces of retrieved context to answer the question.
        If no context is provided, answer the question using your own knowledge, but state that you could not find relevant information in the provided documents.
        Don't make up any information that is not provided in the context. Keep the answer concise.
        
        Context: 
        {context}
        """

    def retrieve(self, state: RAGState) -> Dict:
        """Retrieve relevant documents from the vector store with similarity scores."""
        logger.info({"message": "Starting document retrieval"})
        sources = state.get("sources", [])
        k = state.get("k", 8)  # Allow configurable k

        # Use similarity search with scores
        if sources:
            logger.info({"message": "Attempting retrieval with source filters", "sources": sources})
            retrieved_docs, scores = self.vector_store.get_documents_with_scores(
                state["question"],
                k=k,
                sources=sources
            )
        else:
            logger.info({"message": "No sources specified, searching all documents"})
            retrieved_docs, scores = self.vector_store.get_documents_with_scores(
                state["question"],
                k=k
            )

        # Fallback: if no results with filtering, try without filters
        if not retrieved_docs and sources:
            logger.info({"message": "No documents found with source filtering, trying without filters"})
            retrieved_docs, scores = self.vector_store.get_documents_with_scores(
                state["question"],
                k=k
            )

        # Analyze retrieval results
        if retrieved_docs:
            # Get unique sources and their chunk counts
            source_counts = {}
            for doc in retrieved_docs:
                source = doc.metadata.get("source", "unknown")
                source_counts[source] = source_counts.get(source, 0) + 1

            sources_found = list(source_counts.keys())
            logger.info({
                "message": "Document sources found",
                "sources": sources_found,
                "doc_count": len(retrieved_docs),
                "source_distribution": source_counts,
                "score_range": [min(scores), max(scores)] if scores else []
            })
        else:
            logger.warning({
                "message": "No documents retrieved",
                "query": state["question"],
                "attempted_sources": sources
            })
            scores = []

        return {"context": retrieved_docs, "scores": scores}


    async def generate(self, state: RAGState) -> Dict:
        """Generate an answer using retrieved context."""
        logger.info({
            "message": "Generating answer", 
            "question": state['question']
        })
        
        context = state.get("context", [])
        
        if not context: 
            logger.warning({"message": "No context available for generation", "question": state['question']})
            docs_content = "No relevant documents were found."
        else:
            logger.info({"message": "Generating with context", "context_count": len(context)})
            docs_content = self._hydrate_context(context)

        system_prompt = self.generation_prompt.format(context=docs_content)
        user_message = f"Question: {state['question']}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]

        try:
            response = await self.model_client.chat.completions.create(
                    model=self.model_name,
                    messages=messages,
            )
            response_content = response.choices[0].message.content
            
            logger.info({
                "message": "Generation completed",
                "response_length": len(response_content),
                "response_preview": response_content[:100] + "..."
            })
            
            return {
                "messages": [HumanMessage(content=state["question"]), AIMessage(content=response_content)]
            }
        except Exception as e:
            logger.error({"message": "Error during generation", "error": str(e)})
            fallback_response = f"I apologize, but I encountered an error while processing your query about: {state['question']}"
            return {
                "messages": [HumanMessage(content=state["question"]), AIMessage(content=fallback_response)]
            }

    def _hydrate_context(self, context: List[Document]) -> str:
        """Extract text content from document objects."""
        return "\n\n".join([doc.page_content for doc in context if doc.page_content])

    def _build_graph(self):
        """Build and compile the simplified RAG workflow graph."""
        workflow = StateGraph(RAGState)

        workflow.add_node("retrieve", self.retrieve)
        workflow.add_node("generate", self.generate)
        
        workflow.set_entry_point("retrieve")
        workflow.add_edge("retrieve", "generate")
        workflow.add_edge("generate", END)
        
        return workflow.compile()


mcp = FastMCP("RAG")
rag_agent = RAGAgent()
vector_store = create_vector_store_with_config(rag_agent.config_manager)


@mcp.tool()
async def search_documents(query: str) -> str:
    """Search documents uploaded by the user to generate fast, grounded answers.

    Performs a simple RAG pipeline that retrieves relevant documents and generates answers.

    Args:
        query: The question or query to search for.

    Returns:
        A JSON string with the answer, sources, and retrieval metadata:
        {
            "answer": "...",
            "sources": [
                {
                    "name": "file.pdf",
                    "chunk_count": 3,
                    "max_score": 0.85,
                    "avg_score": 0.72,
                    "chunks": [
                        {"excerpt": "...", "score": 0.85, "text_length": 450},
                        {"excerpt": "...", "score": 0.72, "text_length": 380},
                        {"excerpt": "...", "score": 0.65, "text_length": 420}
                    ]
                }
            ],
            "retrieval_metadata": {
                "total_chunks_retrieved": 8,
                "unique_sources_count": 3,
                "score_range": {"min": 0.45, "max": 0.85, "avg": 0.62},
                "source_filter_applied": ["file1.pdf", "file2.pdf"],
                "query": "..."
            }
        }
    """
    config_obj = rag_agent.config_manager.read_config()
    sources = config_obj.selected_sources or []

    # Allow configurable k (number of chunks to retrieve)
    k = 8  # Default: retrieve top 8 chunks

    initial_state = {
        "question": query,
        "sources": sources,
        "messages": [],
        "k": k
    }
    
    thread_id = f"rag_session_{time.time()}"
    
    result = await rag_agent.graph.ainvoke(initial_state)
    
    if not result.get("messages"):
        logger.error({"message": "No messages in RAG result", "query": query})
        return json.dumps({
            "answer": "I apologize, but I encountered an error processing your query and no response was generated.",
            "sources": []
        })
    
    final_message = result["messages"][-1]
    final_content = getattr(final_message, 'content', '') or ''
    
    if not final_content.strip():
        logger.warning({"message": "Empty content in final RAG message", "query": query, "message_type": type(final_message).__name__})
        return json.dumps({
            "answer": f"I found relevant documents for your query '{query}' but was unable to generate a response. Please try rephrasing your question.",
            "sources": []
        })
    
    # Extract sources from retrieved documents with detailed metadata
    sources_data = []
    context = result.get("context", [])
    scores = result.get("scores", [])

    # Build source distribution map
    source_chunks = {}
    if context:
        for i, doc in enumerate(context):
            source_name = doc.metadata.get("source", "unknown")
            score = scores[i] if i < len(scores) else doc.metadata.get("score", 0.0)

            if source_name not in source_chunks:
                source_chunks[source_name] = {
                    "name": source_name,
                    "chunks": [],
                    "chunk_count": 0,
                    "max_score": 0.0,
                    "avg_score": 0.0
                }

            # Add chunk with score
            chunk_info = {
                "excerpt": doc.page_content[:500] if doc.page_content else "",
                "score": round(score, 4),
                "text_length": len(doc.page_content) if doc.page_content else 0
            }
            source_chunks[source_name]["chunks"].append(chunk_info)
            source_chunks[source_name]["chunk_count"] += 1
            source_chunks[source_name]["max_score"] = max(
                source_chunks[source_name]["max_score"],
                score
            )

        # Calculate average scores
        for source_name, data in source_chunks.items():
            if data["chunks"]:
                data["avg_score"] = round(
                    sum(c["score"] for c in data["chunks"]) / len(data["chunks"]),
                    4
                )
            # Sort chunks by score descending
            data["chunks"].sort(key=lambda x: x["score"], reverse=True)

        sources_data = list(source_chunks.values())

    # Build retrieval metadata
    retrieval_metadata = {
        "total_chunks_retrieved": len(context),
        "unique_sources_count": len(sources_data),
        "score_range": {
            "min": round(min(scores), 4) if scores else None,
            "max": round(max(scores), 4) if scores else None,
            "avg": round(sum(scores) / len(scores), 4) if scores else None
        },
        "source_filter_applied": sources,
        "query": query
    }

    logger.info({
        "message": "RAG result with metadata",
        "content_length": len(final_content),
        "query": query,
        "total_chunks": len(context),
        "unique_sources": len(sources_data),
        "scores": scores[:5] if scores else []
    })

    return json.dumps({
        "answer": final_content,
        "sources": sources_data,
        "retrieval_metadata": retrieval_metadata
    })


if __name__ == "__main__":
    print(f"Starting {mcp.name} MCP server...")
    mcp.run(transport="stdio")
