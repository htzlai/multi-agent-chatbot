#!/usr/bin/env python3
"""
Agent 核心功能测试 - WebSocket 实时对话

专注测试:
1. WebSocket 连接与心跳
2. 流式响应
3. 基础对话功能

使用:
    python3 test_agent.py              # 完整测试 (~2分钟)
    python3 test_agent.py --quick     # 快速测试 (~30秒)
"""

import requests
import json
import time
import sys
import asyncio
import websockets
from datetime import datetime

# 配置
BACKEND_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"

# 快速测试问题
QUICK_QUERIES = [
    "新加坡EP签证要求",
    "ODI备案流程",
]


def print_header(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def test_backend_health():
    """后端健康检查"""
    print_header("1. 后端健康检查")
    
    try:
        resp = requests.get(f"{BACKEND_URL}/knowledge/status", timeout=10)
        data = resp.json()
        print(f"  ✅ 后端正常")
        print(f"     文档: {data['config']['total']} 个")
        print(f"     向量: {data['vectors']['total']} 个")
        return True
    except Exception as e:
        print(f"  ❌ 后端异常: {e}")
        return False


def test_rag_quick():
    """快速 RAG 测试"""
    print_header("2. RAG 快速测试")
    
    for query in QUICK_QUERIES:
        start = time.time()
        try:
            resp = requests.get(
                f"{BACKEND_URL}/test/rag",
                params={"query": query, "k": 5},
                timeout=60
            )
            data = resp.json()
            duration = time.time() - start
            
            sources = len(data.get("sources", []))
            answer_len = len(data.get("answer", ""))
            
            status = "✅" if sources > 0 and answer_len > 50 else "❌"
            print(f"  {status} {query[:20]}: {sources}来源, {answer_len}字, {duration:.1f}s")
            
        except Exception as e:
            print(f"  ❌ {query}: {e}")


async def test_websocket_single(query: str, chat_id: str) -> dict:
    """测试单次 WebSocket 对话"""
    result = {
        "success": False,
        "first_token_time": None,
        "total_time": None,
        "content_length": 0,
        "error": None
    }

    try:
        # 使用更长的超时
        uri = f"{WS_URL}/ws/chat/{chat_id}?heartbeat=60"

        ws = await websockets.connect(uri, ping_interval=None, ping_timeout=120)

        start_time = time.time()

        # 发送消息 - 根据API文档，直接发送message字段
        await ws.send(json.dumps({
            "message": query
        }))

        print(f"     消息已发送，等待响应...")
        
        # 收集响应 (最多60秒)
        token_messages = []
        first_token_time = None
        timeout_count = 0
        max_timeout = 30  # 最多30次
        
        while timeout_count < max_timeout:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                
                try:
                    if isinstance(msg, str):
                        data = json.loads(msg)
                    else:
                        data = msg
                    
                    if not isinstance(data, dict):
                        continue
                    
                    msg_type = data.get("type")

                    # 心跳响应
                    if msg_type == "ping":
                        await ws.send(json.dumps({
                            "type": "pong",
                            "timestamp": data.get("timestamp", 0)
                        }))
                        print(f"     [心跳]")
                        continue

                    # token - 流式输出
                    if msg_type == "token":
                        content = data.get("data", "")
                        if content:
                            if first_token_time is None:
                                first_token_time = time.time() - start_time
                            token_messages.append(content)
                            print(f"     [token] {len(content)}字")

                    # message - 完整消息 (某些后端使用)
                    elif msg_type == "message":
                        content = data.get("content", "")
                        if content:
                            token_messages.append(content)
                            print(f"     [message] {len(content)}字")

                    # history - 消息历史
                    elif msg_type == "history":
                        messages = data.get("messages", [])
                        print(f"     [history] {len(messages)} 条历史消息")

                    # tool_token - 工具输出
                    elif msg_type == "tool_token":
                        content = data.get("content", "")
                        print(f"     [tool_token] {len(content)}字")

                    # node_start/node_end - 节点执行
                    elif msg_type == "node_start":
                        node = data.get("node", "")
                        print(f"     [node_start] {node}")

                    elif msg_type == "node_end":
                        node = data.get("node", "")
                        print(f"     [node_end] {node}")

                    # tool_start/tool_end - 工具执行
                    elif msg_type == "tool_start":
                        tool = data.get("tool", "")
                        print(f"     [tool_start] {tool}")

                    elif msg_type == "tool_end":
                        tool = data.get("tool", "")
                        print(f"     [tool_end] {tool}")

                    # stopped - 生成已停止
                    elif msg_type == "stopped":
                        print(f"     [stopped] 生成完成")
                        break

                    # error - 错误
                    elif msg_type == "error":
                        result["error"] = data.get("content", "Unknown")
                        print(f"     [错误] {result['error']}")
                        break
                
                except json.JSONDecodeError:
                    continue
            
            except asyncio.TimeoutError:
                timeout_count += 1
                if timeout_count % 5 == 0:
                    print(f"     ...等待中 ({timeout_count})")
                continue
        
        result["success"] = True
        result["first_token_time"] = first_token_time
        result["total_time"] = time.time() - start_time
        result["content_length"] = len("".join(token_messages))
        
        await ws.close()
    
    except Exception as e:
        result["error"] = str(e)
        print(f"     异常: {e}")
    
    return result


async def test_websocket_stop():
    """测试 WebSocket 停止生成功能"""
    print_header("3.5 WebSocket 停止生成测试")

    # 创建会话
    try:
        resp = requests.post(f"{BACKEND_URL}/api/v1/chats", timeout=10)
        chat_id = resp.json().get("data", {}).get("chat_id", "test-stop-chat")
    except:
        chat_id = "test-stop-chat"

    print(f"  会话: {chat_id[:8]}...")

    result = {"success": False, "error": None}

    try:
        uri = f"{WS_URL}/ws/chat/{chat_id}?heartbeat=60"
        ws = await websockets.connect(uri, ping_interval=None, ping_timeout=120)

        # 发送一个需要较长时间处理的问题
        await ws.send(json.dumps({
            "message": "请给我讲一个很长的故事，越长越好，包含很多细节"
        }))

        print(f"  发送长查询，等待一些token后停止...")

        # 等待收到几个token后发送停止命令
        token_count = 0
        stop_sent = False

        async for msg in ws:
            try:
                data = json.loads(msg) if isinstance(msg, str) else msg
                msg_type = data.get("type")

                if msg_type == "ping":
                    await ws.send(json.dumps({
                        "type": "pong",
                        "timestamp": data.get("timestamp", 0)
                    }))
                    continue

                if msg_type == "token":
                    token_count += 1
                    # 收到3个token后发送停止命令
                    if token_count >= 3 and not stop_sent:
                        await ws.send(json.dumps({"stop": True}))
                        stop_sent = True
                        print(f"     [已发送停止命令]")

                elif msg_type == "stopped":
                    print(f"     [stopped] 成功停止生成")
                    result["success"] = True
                    break

                elif msg_type == "error":
                    result["error"] = data.get("content", "Unknown")
                    break

            except json.JSONDecodeError:
                continue

        await ws.close()

    except Exception as e:
        result["error"] = str(e)
        print(f"  ❌ 停止测试失败: {e}")

    return result


async def test_websocket_chat():
    """WebSocket 对话测试"""
    print_header("3. WebSocket 实时对话")
    
    # 创建会话
    try:
        resp = requests.post(f"{BACKEND_URL}/chat/new", json={}, timeout=10)
        chat_id = resp.json().get("chat_id", "test-chat")
    except:
        chat_id = "test-quick-chat"
    
    print(f"  会话: {chat_id[:8]}...")
    
    # 测试问题
    test_query = "新加坡EP签证申请要求是什么？"
    print(f"\n  问题: {test_query[:30]}...")
    
    result = await test_websocket_single(test_query, chat_id)
    
    if result["success"]:
        ft = result["first_token_time"]
        print(f"  ✅ 首 token: {ft*1000:.0f}ms" if ft else "  ✅ 首 token: N/A")
        print(f"     总耗时: {result['total_time']:.1f}s")
        print(f"     内容: {result['content_length']} 字")
    else:
        print(f"  ❌ 失败: {result['error']}")
    
    return result


def test_cache():
    """缓存测试"""
    print_header("4. 缓存测试")
    
    query = "缓存测试专用查询"
    
    # 第一次
    start = time.time()
    requests.post(
        f"{BACKEND_URL}/rag/llamaindex/query",
        json={"query": query, "use_cache": True},
        timeout=30
    )
    first = time.time() - start
    
    # 第二次 (缓存)
    start = time.time()
    requests.post(
        f"{BACKEND_URL}/rag/llamaindex/query",
        json={"query": query, "use_cache": True},
        timeout=30
    )
    cached = time.time() - start
    
    speedup = first / cached if cached > 0 else 0
    
    print(f"  首次: {first*1000:.0f}ms")
    print(f"  缓存: {cached*1000:.0f}ms")
    print(f"  加速: {speedup:.1f}x {'✅' if speedup > 2 else '⚠️'}")


async def run_quick():
    """快速测试"""
    print("\n" + "=" * 60)
    print("  Agent 快速测试 (~30秒)")
    print("=" * 60)
    
    # 1. 健康检查
    if not test_backend_health():
        return
    
    # 2. RAG 快速测试
    test_rag_quick()
    
    # 3. WebSocket 测试
    ws_result = await test_websocket_chat()
    
    # 4. 缓存测试
    test_cache()
    
    # 总结
    print_header("测试结果")
    
    if ws_result["success"]:
        print("  ✅ WebSocket 对话: 正常")
    else:
        print(f"  ❌ WebSocket: {ws_result.get('error', '失败')}")
    
    print(f"  ✅ 测试完成")


async def run_full():
    """完整测试"""
    print("\n" + "=" * 60)
    print("  Agent 完整测试 (~2分钟)")
    print("=" * 60)

    # 1. 健康检查
    if not test_backend_health():
        return

    # 2. RAG 测试
    test_rag_quick()

    # 3. WebSocket 测试 (多次)
    print("\n  【多次对话测试】")
    for i in range(3):
        ws_result = await test_websocket_chat()
        status = "✅" if ws_result["success"] else "❌"
        print(f"    第{i+1}次: {status}")

    # 3.5 停止生成测试
    print("\n  【停止生成测试】")
    stop_result = await test_websocket_stop()
    stop_status = "✅" if stop_result["success"] else "❌"
    print(f"    停止生成: {stop_status}")

    # 4. 缓存测试
    test_cache()

    print("\n  ✅ 完整测试完成")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--quick"
    
    if mode == "--quick":
        asyncio.run(run_quick())
    else:
        asyncio.run(run_full())


if __name__ == "__main__":
    main()
