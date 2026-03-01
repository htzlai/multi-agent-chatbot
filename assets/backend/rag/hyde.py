# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""HyDE (Hypothetical Document Embeddings) query expansion.

Generates a hypothetical answer document via LLM, then uses it alongside
the original query for retrieval — typically improves recall 10-15%.

Fully async — uses the shared ``infrastructure.llm_client`` singleton
instead of creating a new event-loop per call.
"""

import logging
from functools import lru_cache
from typing import List, Optional

from infrastructure.llm_client import get_llm_client, get_llm_model

logger = logging.getLogger(__name__)

_HYDE_SYSTEM = "你是一个专业的文档生成助手。"

_HYDE_PROMPT_TEMPLATE = """你是一个专业的问答系统。请根据用户的问题，生成一个假设的文档片段，这个片段应该能够回答用户的问题。

要求：
1. 用中文回答
2. 假设你是相关领域的专家
3. 生成一个详细的、能够回答问题的文档片段

用户问题：{query}

假设文档："""


class HyDEQueryExpander:
    """Async HyDE query expansion via the shared LLM client."""

    def __init__(self, max_hypothetical_docs: int = 1):
        self.max_hypothetical_docs = max_hypothetical_docs

    async def expand(self, query: str) -> List[str]:
        """Return ``[original_query, hypothetical_doc, ...]``.

        Falls back to ``[query]`` on any failure.
        """
        client = get_llm_client()
        model = get_llm_model()

        try:
            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _HYDE_SYSTEM},
                    {
                        "role": "user",
                        "content": _HYDE_PROMPT_TEMPLATE.format(query=query),
                    },
                ],
                max_tokens=500,
                temperature=0.3,
            )

            hypothetical_doc = response.choices[0].message.content
            return [query, hypothetical_doc]

        except Exception as e:
            logger.warning(f"HyDE query expansion failed: {e}")
            return [query]


# ------------------------------------------------------------------
# Module-level helpers
# ------------------------------------------------------------------


@lru_cache()
def get_hyde_expander() -> HyDEQueryExpander:
    """Return the shared ``HyDEQueryExpander`` singleton."""
    return HyDEQueryExpander()


async def expand_query_with_hyde(
    query: str,
    use_hyde: bool = True,
) -> List[str]:
    """Expand *query* via HyDE if enabled."""
    if not use_hyde:
        return [query]

    expander = get_hyde_expander()
    return await expander.expand(query)
