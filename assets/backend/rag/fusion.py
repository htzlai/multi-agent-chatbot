# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""Reciprocal Rank Fusion (RRF) for merging ranked result lists.

Pure function — no external dependencies, no state.
"""

from collections import defaultdict
from typing import Dict, List


def reciprocal_rank_fusion(
    vector_results: List[Dict],
    bm25_results: List[Dict],
    k: int = 60,
) -> List[Dict]:
    """Merge vector and BM25 search results using RRF.

    RRF formula: ``score = sum(1 / (k + rank))`` across result lists.

    Args:
        vector_results: Ranked vector search results (must have ``name`` key).
        bm25_results: Ranked BM25 search results (must have ``name`` key).
        k: Smoothing constant (higher = less weight to top ranks).

    Returns:
        Fused list sorted by descending RRF score.
    """
    source_scores: Dict[str, Dict] = defaultdict(
        lambda: {
            "vector_rank": None,
            "bm25_rank": None,
            "vector_score": 0,
            "bm25_score": 0,
            "excerpt": "",
        }
    )

    for rank, item in enumerate(vector_results):
        source = item.get("name", "")
        if source:
            source_scores[source]["vector_rank"] = rank + 1
            source_scores[source]["vector_score"] = item.get("score", 0)
            source_scores[source]["excerpt"] = item.get("excerpt", "")

    for rank, item in enumerate(bm25_results):
        source = item.get("name", "")
        if source:
            source_scores[source]["bm25_rank"] = rank + 1
            source_scores[source]["bm25_score"] = item.get("score", 0)
            if not source_scores[source]["excerpt"]:
                source_scores[source]["excerpt"] = item.get("excerpt", "")

    fused: List[Dict] = []
    for source, scores in source_scores.items():
        rrf_score = 0.0
        if scores["vector_rank"] is not None:
            rrf_score += 1.0 / (k + scores["vector_rank"])
        if scores["bm25_rank"] is not None:
            rrf_score += 1.0 / (k + scores["bm25_rank"])

        fused.append(
            {
                "name": source,
                "score": rrf_score,
                "vector_score": scores["vector_score"],
                "bm25_score": scores["bm25_score"],
                "excerpt": scores["excerpt"],
            }
        )

    fused.sort(key=lambda x: x["score"], reverse=True)
    return fused
