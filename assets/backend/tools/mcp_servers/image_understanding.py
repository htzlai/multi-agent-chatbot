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

"""
MCP server providing image understanding and analysis tools.

This server exposes a `process_image` tool that uses a vision language model to answer queries about images. 
It supports multiple image input formats including URLs, file paths, and base64-encoded images.
"""
import base64
import os
import sys
from functools import lru_cache
from pathlib import Path

from mcp.server.fastmcp import FastMCP
from openai import OpenAI

project_root = Path(__file__).parent.parent.parent
sys.path.append(str(project_root))


mcp = FastMCP("image-understanding-server")

# --- Configuration from environment ---
VLM_MODEL_NAME = os.getenv("VLM_MODEL_NAME", "")
VLM_BASE_URL = os.getenv("VLM_BASE_URL", "")
VLM_API_KEY = os.getenv("VLM_API_KEY", "api_key")


def _is_vlm_configured() -> bool:
    """Check if VLM service is configured."""
    return bool(VLM_BASE_URL and VLM_MODEL_NAME)


@lru_cache()
def get_model_client() -> OpenAI | None:
    """Singleton OpenAI client for VLM model. Returns None if not configured."""
    if not _is_vlm_configured():
        return None
    return OpenAI(base_url=VLM_BASE_URL, api_key=VLM_API_KEY)

@mcp.tool()
def explain_image(query: str, image: str):
    """
    This tool is used to understand an image. It will respond to the user's query based on the image.
    ...
    """ 
    if not image:
        raise ValueError('Error: explain_image tool received an empty image string.')

    image_url_content = {}

    if image.startswith("http://") or image.startswith("https://"):
        image_url_content = {
            "type": "image_url",
            "image_url": {"url": image}
        }
    else:
        if image.startswith("data:image/"):
            metadata, b64_data = image.split(",", 1)
            filetype = metadata.split(";")[0].split("/")[-1]
        elif os.path.exists(image):
            with open(image, "rb") as image_file:
                filetype = image.split('.')[-1]
                b64_data = base64.b64encode(image_file.read()).decode("utf-8")
        else:
            raise ValueError(f'Invalid image type -- could not be identified as a url or filepath: {image}')
        
        image_url_content = {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/{filetype if filetype else 'jpeg'};base64,{b64_data}"
            }
        }

    message = [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": query},
                image_url_content
            ]
        }
    ]
    
    client = get_model_client()
    if client is None:
        return (
            "[Image analysis unavailable] "
            "Vision language model is not configured. "
            "Set VLM_BASE_URL and VLM_MODEL_NAME environment variables to enable image understanding."
        )

    try:
        print(f"Sending request to vision model: {query}")
        response = client.chat.completions.create(
            model=VLM_MODEL_NAME,
            messages=message,
            max_tokens=512,
            temperature=0.1
        )
        print(f"Received response from vision model")
        return response.choices[0].message.content
    except Exception as e:
        print(f"Error calling vision model: {e}")
        return (
            f"[Image analysis failed] "
            f"Could not reach vision model at {VLM_BASE_URL}: {e}. "
            f"The model service may be unavailable."
        )

if __name__ == "__main__":
    print(f'running {mcp.name} MCP server')
    mcp.run(transport="stdio")