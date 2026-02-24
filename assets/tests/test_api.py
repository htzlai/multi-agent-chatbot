#!/usr/bin/env python3
"""
后端 API 全面测试脚本

覆盖所有 API 端点:
1. RESTful API v1 (推荐)
2. OpenAI 兼容 API
3. WebSocket 实时通信
4. LlamaIndex RAG
5. 知识库管理

使用:
    python3 test_api.py              # 完整测试 (~3分钟)
    python3 test_api.py --quick     # 快速测试 (~1分钟)
    python3 test_api.py --v1        # 仅测试 v1 API
    python3 test_api.py --rag       # 仅测试 RAG
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


def print_header(title: str):
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


# ============================================================
# 测试 1: 健康检查
# ============================================================

def test_health():
    """后端健康检查"""
    print_header("1. 后端健康检查")
    
    try:
        # 知识库状态
        r = requests.get(f"{BACKEND_URL}/knowledge/status", timeout=10)
        data = r.json()
        print(f"  ✅ /knowledge/status")
        print(f"     文档: {data['config']['total']}, 向量: {data['vectors']['total']}")
        
        # 可用模型
        r = requests.get(f"{BACKEND_URL}/available_models", timeout=10)
        models = r.json()
        print(f"  ✅ /available_models")
        
        # 选中的模型
        r = requests.get(f"{BACKEND_URL}/selected_model", timeout=10)
        print(f"  ✅ /selected_model")
        
        return True
    except Exception as e:
        print(f"  ❌ 健康检查失败: {e}")
        return False


# ============================================================
# 测试 2: RESTful API v1 - 会话管理
# ============================================================

def test_v1_chats():
    """测试 RESTful API v1 会话管理"""
    print_header("2. RESTful API v1 - 会话管理")
    
    results = []
    
    # 1. 创建新会话
    try:
        r = requests.post(f"{BACKEND_URL}/api/v1/chats", timeout=10)
        data = r.json()
        chat_id = data.get("data", {}).get("chat_id")
        print(f"  ✅ POST /api/v1/chats: {chat_id[:8]}...")
        results.append(("create_chat", True, chat_id))
    except Exception as e:
        print(f"  ❌ POST /api/v1/chats: {e}")
        results.append(("create_chat", False, str(e)))
        return results
    
    # 2. 获取所有会话
    try:
        r = requests.get(f"{BACKEND_URL}/api/v1/chats", timeout=10)
        data = r.json()
        print(f"  ✅ GET /api/v1/chats: {len(data.get('data', []))} 个会话")
        results.append(("list_chats", True, None))
    except Exception as e:
        print(f"  ❌ GET /api/v1/chats: {e}")
        results.append(("list_chats", False, str(e)))
    
    # 3. 获取当前会话
    try:
        r = requests.get(f"{BACKEND_URL}/api/v1/chats/current", timeout=10)
        data = r.json()
        print(f"  ✅ GET /api/v1/chats/current")
        results.append(("get_current", True, None))
    except Exception as e:
        print(f"  ❌ GET /api/v1/chats/current: {e}")
        results.append(("get_current", False, str(e)))
    
    # 4. 更新当前会话
    try:
        r = requests.patch(
            f"{BACKEND_URL}/api/v1/chats/current",
            json={"chat_id": chat_id},
            timeout=10
        )
        print(f"  ✅ PATCH /api/v1/chats/current")
        results.append(("update_current", True, None))
    except Exception as e:
        print(f"  ❌ PATCH /api/v1/chats/current: {e}")
        results.append(("update_current", False, str(e)))
    
    # 5. 获取会话消息
    try:
        r = requests.get(f"{BACKEND_URL}/api/v1/chats/{chat_id}/messages", timeout=10)
        data = r.json()
        print(f"  ✅ GET /api/v1/chats/{{id}}/messages")
        results.append(("get_messages", True, None))
    except Exception as e:
        print(f"  ❌ GET /api/v1/chats/{{id}}/messages: {e}")
        results.append(("get_messages", False, str(e)))
    
    # 6. 获取会话元数据
    try:
        r = requests.get(f"{BACKEND_URL}/api/v1/chats/{chat_id}/metadata", timeout=10)
        data = r.json()
        print(f"  ✅ GET /api/v1/chats/{{id}}/metadata")
        results.append(("get_metadata", True, None))
    except Exception as e:
        print(f"  ❌ GET /api/v1/chats/{{id}}/metadata: {e}")
        results.append(("get_metadata", False, str(e)))
    
    # 7. 更新会话元数据 (重命名)
    try:
        r = requests.patch(
            f"{BACKEND_URL}/api/v1/chats/{chat_id}/metadata",
            json={"title": "测试会话"},
            timeout=10
        )
        print(f"  ✅ PATCH /api/v1/chats/{{id}}/metadata")
        results.append(("rename_chat", True, None))
    except Exception as e:
        print(f"  ❌ PATCH /api/v1/chats/{{id}}/metadata: {e}")
        results.append(("rename_chat", False, str(e)))

    # 8. 删除指定会话
    try:
        r = requests.delete(f"{BACKEND_URL}/api/v1/chats/{chat_id}", timeout=10)
        print(f"  ✅ DELETE /api/v1/chats/{{id}}")
        results.append(("delete_chat", True, None))
    except Exception as e:
        print(f"  ❌ DELETE /api/v1/chats/{{id}}: {e}")
        results.append(("delete_chat", False, str(e)))

    return results, chat_id


# ============================================================
# 测试 3: RESTful API v1 - 知识源管理
# ============================================================

def test_v1_sources():
    """测试知识源管理 API"""
    print_header("3. RESTful API v1 - 知识源管理")
    
    results = []
    
    # 1. 获取所有文档源
    try:
        r = requests.get(f"{BACKEND_URL}/api/v1/sources", timeout=10)
        data = r.json()
        sources = data.get("data", [])
        print(f"  ✅ GET /api/v1/sources: {len(sources)} 个文档")
        results.append(("list_sources", True, len(sources)))
    except Exception as e:
        print(f"  ❌ GET /api/v1/sources: {e}")
        results.append(("list_sources", False, str(e)))
    
    # 2. 获取选中的源
    try:
        r = requests.get(f"{BACKEND_URL}/api/v1/selected-sources", timeout=10)
        data = r.json()
        selected = data.get("data", [])
        print(f"  ✅ GET /api/v1/selected-sources: {len(selected)} 个选中")
        results.append(("get_selected", True, len(selected)))
    except Exception as e:
        print(f"  ❌ GET /api/v1/selected-sources: {e}")
        results.append(("get_selected", False, str(e)))
    
    # 3. 设置选中的源 (测试设置前3个)
    try:
        test_sources = sources[:3] if len(sources) >= 3 else sources
        r = requests.post(
            f"{BACKEND_URL}/api/v1/selected-sources",
            json={"sources": test_sources},
            timeout=10
        )
        print(f"  ✅ POST /api/v1/selected-sources: 设置 {len(test_sources)} 个")
        results.append(("set_selected", True, len(test_sources)))
    except Exception as e:
        print(f"  ❌ POST /api/v1/selected-sources: {e}")
        results.append(("set_selected", False, str(e)))

    # 4. 重建索引 (POST /api/v1/sources:reindex)
    try:
        test_source = sources[0] if sources else "test.pdf"
        r = requests.post(
            f"{BACKEND_URL}/api/v1/sources:reindex",
            json={"sources": [test_source]},
            timeout=30
        )
        data = r.json()
        task_id = data.get("data", {}).get("task_id")
        status = data.get("data", {}).get("status")
        print(f"  ✅ POST /api/v1/sources:reindex: task_id={task_id}, status={status}")
        results.append(("reindex", True, task_id))
    except Exception as e:
        print(f"  ❌ POST /api/v1/sources:reindex: {e}")
        results.append(("reindex", False, str(e)))

    return results


# ============================================================
# 测试 4: OpenAI 兼容 API
# ============================================================

def test_openai_api():
    """测试 OpenAI 兼容 API"""
    print_header("4. OpenAI 兼容 API")
    
    results = []
    
    # 1. 获取模型列表
    try:
        r = requests.get(f"{BACKEND_URL}/v1/models", timeout=10)
        data = r.json()
        models = data.get("data", [])
        print(f"  ✅ GET /v1/models: {len(models)} 个模型")
        for m in models:
            print(f"     - {m.get('id')}")
        results.append(("list_models", True, len(models)))
    except Exception as e:
        print(f"  ❌ GET /v1/models: {e}")
        results.append(("list_models", False, str(e)))
    
    # 2. 创建 Embedding
    try:
        r = requests.post(
            f"{BACKEND_URL}/v1/embeddings",
            json={"model": "qwen3-embedding", "input": "测试文本"},
            timeout=30
        )
        data = r.json()
        embedding = data.get("data", [{}])[0].get("embedding", [])
        print(f"  ✅ POST /v1/embeddings: {len(embedding)} 维")
        results.append(("create_embedding", True, len(embedding)))
    except Exception as e:
        print(f"  ❌ POST /v1/embeddings: {e}")
        results.append(("create_embedding", False, str(e)))

    # 3. 流式聊天完成 (SSE)
    try:
        import threading
        token_count = 0
        content = ""
        done = threading.Event()

        def stream_listener():
            nonlocal token_count, content
            r = requests.post(
                f"{BACKEND_URL}/v1/chat/completions",
                json={
                    "model": "gpt-oss-120b",
                    "messages": [{"role": "user", "content": "你好"}],
                    "stream": True
                },
                stream=True,
                timeout=60
            )
            for line in r.iter_lines():
                if line:
                    line = line.decode('utf-8')
                    if line.startswith('data: '):
                        data_str = line[6:]
                        if data_str == '[DONE]':
                            done.set()
                            break
                        try:
                            import json
                            data_json = json.loads(data_str)
                            delta = data_json.get("choices", [{}])[0].get("delta", {})
                            token = delta.get("content", "")
                            if token:
                                token_count += 1
                                content += token
                        except:
                            pass

        thread = threading.Thread(target=stream_listener)
        thread.start()
        thread.join(timeout=30)

        print(f"  ✅ POST /v1/chat/completions (stream): {token_count} tokens, {len(content)} 字")
        results.append(("stream_chat", True, token_count))
    except Exception as e:
        print(f"  ❌ POST /v1/chat/completions (stream): {e}")
        results.append(("stream_chat", False, str(e)))

    return results


# ============================================================
# 测试 5: RAG 检索
# ============================================================

def test_rag():
    """测试 RAG 检索"""
    print_header("5. RAG 检索测试")
    
    results = []
    
    # 1. 标准 RAG
    try:
        start = time.time()
        r = requests.get(
            f"{BACKEND_URL}/test/rag",
            params={"query": "新加坡EP签证", "k": 5},
            timeout=60
        )
        duration = time.time() - start
        data = r.json()
        sources = data.get("sources", [])
        answer = data.get("answer", "")
        print(f"  ✅ 标准 RAG: {len(sources)} 来源, {len(answer)} 字, {duration:.1f}s")
        results.append(("standard_rag", True, duration))
    except Exception as e:
        print(f"  ❌ 标准 RAG: {e}")
        results.append(("standard_rag", False, str(e)))
    
    # 2. LlamaIndex RAG
    try:
        start = time.time()
        r = requests.post(
            f"{BACKEND_URL}/rag/llamaindex/query",
            json={"query": "新加坡EP签证", "top_k": 5, "use_cache": False},
            timeout=60
        )
        duration = time.time() - start
        data = r.json()
        sources = data.get("sources", [])
        answer = data.get("answer", "")
        print(f"  ✅ LlamaIndex RAG: {len(sources)} 来源, {len(answer)} 字, {duration:.1f}s")
        results.append(("llamaindex_rag", True, duration))
    except Exception as e:
        print(f"  ❌ LlamaIndex RAG: {e}")
        results.append(("llamaindex_rag", False, str(e)))
    
    # 3. LlamaIndex 配置
    try:
        r = requests.get(f"{BACKEND_URL}/rag/llamaindex/config", timeout=10)
        data = r.json()
        features = data.get("features", {})
        print(f"  ✅ LlamaIndex 配置: {features}")
        results.append(("llamaindex_config", True, None))
    except Exception as e:
        print(f"  ❌ LlamaIndex 配置: {e}")
        results.append(("llamaindex_config", False, str(e)))
    
    # 4. 缓存测试
    try:
        q = "缓存测试查询"
        # 第一次
        r1 = requests.post(
            f"{BACKEND_URL}/rag/llamaindex/query",
            json={"query": q, "use_cache": True},
            timeout=30
        )
        # 第二次
        r2 = requests.post(
            f"{BACKEND_URL}/rag/llamaindex/query",
            json={"query": q, "use_cache": True},
            timeout=30
        )
        t1 = r1.elapsed.total_seconds() * 1000
        t2 = r2.elapsed.total_seconds() * 1000
        speedup = t1 / t2 if t2 > 0 else 0
        print(f"  ✅ 缓存: 首次 {t1:.0f}ms, 缓存 {t2:.0f}ms, 加速 {speedup:.1f}x")
        results.append(("cache", True, speedup))
    except Exception as e:
        print(f"  ❌ 缓存: {e}")
        results.append(("cache", False, str(e)))
    
    return results


# ============================================================
# 测试 6: WebSocket
# ============================================================

async def test_websocket():
    """测试 WebSocket"""
    print_header("6. WebSocket 实时通信")
    
    # 创建会话
    try:
        r = requests.post(f"{BACKEND_URL}/api/v1/chats", timeout=10)
        chat_id = r.json().get("data", {}).get("chat_id")
        print(f"  会话: {chat_id[:8]}...")
    except:
        chat_id = "test-websocket"
    
    result = {"success": False}
    
    try:
        uri = f"{WS_URL}/ws/chat/{chat_id}?heartbeat=60"
        ws = await websockets.connect(uri, ping_interval=None)
        
        # 发送消息
        await ws.send(json.dumps({
            "type": "message",
            "message": "测试"
        }))
        
        # 接收响应
        token_count = 0
        async for msg in ws:
            data = json.loads(msg)
            if data.get("type") == "token":
                token_count += 1
            elif data.get("type") in ["node_end", "stopped"]:
                break
        
        await ws.close()
        
        print(f"  ✅ WebSocket: 收到 {token_count} 个 token")
        result = {"success": True, "tokens": token_count}
        
    except Exception as e:
        print(f"  ❌ WebSocket: {e}")
        result = {"success": False, "error": str(e)}
    
    return result


# ============================================================
# 测试 7: 管理员 API
# ============================================================

def test_admin():
    """测试管理员 API"""
    print_header("7. 管理员 API")
    
    results = []
    
    # 1. RAG 统计
    try:
        r = requests.get(f"{BACKEND_URL}/admin/rag/stats", timeout=10)
        data = r.json()
        print(f"  ✅ GET /admin/rag/stats")
        results.append(("rag_stats", True, None))
    except Exception as e:
        print(f"  ❌ GET /admin/rag/stats: {e}")
        results.append(("rag_stats", False, str(e)))
    
    # 2. 源管理
    try:
        r = requests.get(f"{BACKEND_URL}/admin/rag/sources", timeout=10)
        data = r.json()
        print(f"  ✅ GET /admin/rag/sources")
        results.append(("rag_sources", True, None))
    except Exception as e:
        print(f"  ❌ GET /admin/rag/sources: {e}")
        results.append(("rag_sources", False, str(e)))
    
    # 3. 知识库状态
    try:
        r = requests.get(f"{BACKEND_URL}/knowledge/status", timeout=10)
        data = r.json()
        summary = data.get("summary", {})
        print(f"  ✅ /knowledge/status: {summary}")
        results.append(("knowledge_status", True, None))
    except Exception as e:
        print(f"  ❌ /knowledge/status: {e}")
        results.append(("knowledge_status", False, str(e)))
    
    return results


# ============================================================
# 汇总报告
# ============================================================

def generate_report(all_results: dict):
    """生成测试报告"""
    print_header("测试报告")
    
    total = 0
    passed = 0
    
    for category, results in all_results.items():
        if isinstance(results, dict):
            # WebSocket 结果
            total += 1
            if results.get("success"):
                passed += 1
        else:
            # 列表结果
            for name, success, _ in results:
                total += 1
                if success:
                    passed += 1
    
    pass_rate = (passed / total * 100) if total > 0 else 0
    
    print(f"\n  总计: {total} | 通过: {passed} | 失败: {total-passed}")
    print(f"  通过率: {pass_rate:.1f}%")
    
    if pass_rate >= 90:
        print(f"  评级: 🎉 A (优秀)")
    elif pass_rate >= 75:
        print(f"  评级: ✅ B (良好)")
    elif pass_rate >= 60:
        print(f"  评级: ⚠️ C (及格)")
    else:
        print(f"  评级: ❌ D (需改进)")


# ============================================================
# 主函数
# ============================================================

async def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "--full"
    
    print("\n" + "=" * 60)
    print("  后端 API 全面测试")
    print(f"  模式: {mode}")
    print("=" * 60)
    
    all_results = {}
    
    # 1. 健康检查
    if not test_health():
        print("\n  ❌ 后端不可用，退出测试")
        return 1
    
    # 2. RESTful API v1
    if mode in ["--full", "--v1"]:
        results, chat_id = test_v1_chats()
        all_results["v1_chats"] = results
        
        sources_results = test_v1_sources()
        all_results["v1_sources"] = sources_results
    
    # 3. OpenAI API
    if mode in ["--full", "--openai"]:
        openai_results = test_openai_api()
        all_results["openai"] = openai_results
    
    # 4. RAG
    if mode in ["--full", "--rag"]:
        rag_results = test_rag()
        all_results["rag"] = rag_results
    
    # 5. WebSocket
    if mode in ["--full", "--ws"]:
        ws_result = await test_websocket()
        all_results["websocket"] = ws_result
    
    # 6. 管理员
    if mode in ["--full", "--admin"]:
        admin_results = test_admin()
        all_results["admin"] = admin_results
    
    # 报告
    generate_report(all_results)
    
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
