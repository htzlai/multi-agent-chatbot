# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""ChatAgent package — LLM-powered conversational AI with tool calling.

Public API::

    from agent import ChatAgent
"""

from agent.core import ChatAgent
from agent.streaming import SENTINEL, StreamCallback

__all__ = ["ChatAgent", "SENTINEL", "StreamCallback"]
