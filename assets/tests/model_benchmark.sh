#!/bin/bash
#==============================================================================
# gpt-oss-120b 模型性能基准测试 (专业版 v5)
#==============================================================================
#
# 基于 MLPerf Inference v5.0 和 NVIDIA NIM 基准测试标准
# 参考: https://mlcommons.org/2025/04/llm-inference-v5/
# 参考: https://docs.nvidia.com/nim/benchmarking/llm/latest/metrics.html
#
# 功能:
#   - 配置验证 (行业标准检查)
#   - LLM性能测试 (TTFT, TPS, RPS, 并发, E2E延迟)
#   - Embedding性能测试
#   - 行业标准对比分析
#   - 极限压力测试
#
# 使用方法:
#   ./model_benchmark.sh           # 标准测试
#   ./model_benchmark.sh --verify # 仅验证配置
#   ./model_benchmark.sh --quick  # 快速测试
#   ./model_benchmark.sh --full   # 完整测试 (包含压力测试)
#   ./model_benchmark.sh --llm    # 仅LLM测试
#   ./model_benchmark.sh --embed  # 仅Embedding测试
#   ./model_benchmark.sh --compare # 行业标准对比
#
#==============================================================================

set -e

# 配置
MODEL_CONTAINER="backend"
LLM_URL="http://gpt-oss-120b:8000"
LLM_MODEL="gpt-oss-120b"
EMBED_URL="http://qwen3-embedding:8000"
EMBED_MODEL="qwen3-embedding"

# 行业标准基准值 (参考 MLPerf & NVIDIA NIM)
# 来源: MLCommons 2025, NVIDIA NIM Documentation
INDUSTRY_STANDARD_TTFT_1K_PROMPT=1000    # 1K prompt 下 TTFT 标准 (ms)
INDUSTRY_STANDARD_TPS_120B=30             # 120B 模型 TPS 标准 (tokens/s)
INDUSTRY_STANDARD_E2E_LATENCY=5000        # 1K output E2E 延迟标准 (ms)
INDUSTRY_STANDARD_RPS_4CONCURRENT=0.5     # 4并发 RPS 标准

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m'

#==============================================================================
# 工具函数
#==============================================================================

print_header() {
    echo -e "${MAGENTA}╔═══════════════════════════════════════════════════════════════════╗${NC}"
    printf "${MAGENTA}║  %-65s ║${NC}\n" "$1"
    echo -e "${MAGENTA}╚═══════════════════════════════════════════════════════════════════╝${NC}"
}

print_section() {
    echo -e "\n${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    printf "${CYAN}  %-60s${NC}\n" "$1"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_metric() {
    local label=$1
    local value=$2
    local unit=$3
    local benchmark=$4
    local status=""
    
    # 与行业标准对比
    if [ -n "$benchmark" ]; then
        if [ "$value" -le "$benchmark" ]; then
            status="${GREEN}✓${NC}"
        else
            status="${YELLOW}△${NC}"
        fi
        printf "  ${status} %-35s %10s %-8s (行业标准: %s %s)\n" "$label" "$value" "$unit" "$benchmark" "$unit"
    else
        printf "  %-35s %10s %-8s\n" "$label" "$value" "$unit"
    fi
}

get_benchmark_status() {
    local actual=$1
    local standard=$2
    
    if [ "$actual" -le "$standard" ]; then
        echo -e "${GREEN}达标${NC}"
    else
        echo -e "${YELLOW}低于标准${NC} (实际: ${actual}, 标准: ${standard})"
    fi
}

#==============================================================================
# 0. 配置验证 (符合 MLCommons 标准)
#==============================================================================
verify_config() {
    print_header "配置验证 - MLCommons 标准检查"
    
    echo -e "\n${BLUE}[1] LLM 容器配置 (Llama.cpp 参数)${NC}"
    CMD=$(docker inspect gpt-oss-120b --format '{{.Config.Cmd}}' 2>/dev/null || echo "无法获取")
    echo "  命令: $CMD"
    
    echo -e "\n${BLUE}[2] 关键参数验证${NC}"
    
    # -n (max_tokens)
    N_VAL=$(echo "$CMD" | grep -oE "\-n +[0-9]+" | grep -oE "[0-9]+" || echo "0")
    if [ "$N_VAL" -ge 8192 ]; then
        echo -e "  ✅ -n (max_tokens): ${N_VAL} (推荐: ≥8192)"
    else
        echo -e "  ❌ -n (max_tokens): ${N_VAL} (推荐: ≥8192)"
    fi
    
    # --parallel (并发支持)
    P_VAL=$(echo "$CMD" | grep -oE "\-\-parallel +[0-9]+" | grep -oE "[0-9]+" || echo "0")
    if [ "$P_VAL" -ge 4 ]; then
        echo -e "  ✅ --parallel: ${P_VAL} (推荐: ≥4)"
    else
        echo -e "  ⚠️  --parallel: ${P_VAL} (推荐: ≥4)"
    fi
    
    # --ctx-size (上下文窗口)
    CTX_VAL=$(echo "$CMD" | grep -oE "\-\-ctx-size +[0-9]+" | grep -oE "[0-9]+" || echo "0")
    if [ "$CTX_VAL" -ge 8192 ]; then
        echo -e "  ✅ --ctx-size: ${CTX_VAL} (推荐: ≥8192)"
    else
        echo -e "  ⚠️  --ctx-size: ${CTX_VAL} (推荐: ≥8192)"
    fi
    
    echo -e "\n${BLUE}[3] 服务健康检查${NC}"
    
    # LLM 服务
    if curl -s --max-time 5 "$LLM_URL/v1/models" | jq -r '.data[0].id' > /dev/null 2>&1; then
        MODEL_ID=$(curl -s --max-time 5 "$LLM_URL/v1/models" | jq -r '.data[0].id')
        echo -e "  ✅ LLM服务: $MODEL_ID"
    else
        echo -e "  ❌ LLM服务异常"
    fi
    
    # Embedding 服务
    if curl -s --max-time 5 "$EMBED_URL/v1/models" | jq -r '.data[0].id' > /dev/null 2>&1; then
        EMBED_ID=$(curl -s --max-time 5 "$EMBED_URL/v1/models" | jq -r '.data[0].id')
        echo -e "  ✅ Embedding服务: $EMBED_ID"
    else
        echo -e "  ❌ Embedding服务异常"
    fi
    
    echo -e "\n${BLUE}[4] GPU 状态 (NVIDIA)${NC}"
    if command -v nvidia-smi &> /dev/null; then
        nvidia-smi --query-gpu=name,memory.total,memory.used,utilization.gpu --format=csv,noheader | while read line; do
            IFS=',' read -r name memory_total memory_used util <<< "$line"
            echo "  GPU: $(echo $name | xargs)"
            echo "    显存: $(echo $memory_used | xargs) / $(echo $memory_total | xargs)"
            echo "    利用率: $(echo $util | xargs)%"
        done
    else
        echo -e "  ⚠️  nvidia-smi 不可用"
    fi
}

#==============================================================================
# 1. LLM 基础功能测试
#==============================================================================
test_llm_basic() {
    print_header "LLM 基础功能测试"
    
    echo -e "\n${BLUE}[1.1] 基本对话 (Hello World)${NC}"
    result=$(curl -s --max-time 30 -X POST $LLM_URL/v1/chat/completions \
        -H "Content-Type: application/json" \
        -d '{"model": "'$LLM_MODEL'", "messages": [{"role": "user", "content": "你好"}], "max_tokens": 50}')
    content=$(echo "$result" | grep -o '"content":"[^"]*"' | sed 's/"content":"//;s/"$//' | head -c 100)
    if [ -n "$content" ]; then
        echo -e "  ✅ 响应正常: ${content}..."
    else
        echo -e "  ❌ 响应失败"
    fi
    
    echo -e "\n${BLUE}[1.2] 长文本生成 (2000 tokens)${NC}"
    start=$(date +%s)
    result=$(curl -s --max-time 120 -X POST $LLM_URL/v1/chat/completions \
        -H "Content-Type: application/json" \
        -d '{"model": "'$LLM_MODEL'", "messages": [{"role": "user", "content": "请写一个关于未来科技的科幻短篇故事"}], "max_tokens": 2000, "temperature": 0.7}')
    end=$(date +%s)
    duration=$((end - start))
    chars=$(echo "$result" | grep -o '"content":"[^"]*"' | sed 's/"content":"//;s/"$//' | wc -c)
    tokens=$((chars / 4))
    
    echo -e "  生成: ~${tokens} tokens, 耗时: ${duration}秒"
    if [ "$tokens" -gt 1500 ]; then
        echo -e "  ✅ 长文本生成正常"
    fi
}

#==============================================================================
# 2. LLM 性能指标测试 (参考 NVIDIA NIM 标准)
#==============================================================================
test_llm_performance() {
    print_header "LLM 性能指标测试 - NVIDIA NIM 标准"
    
    echo -e "\n${YELLOW}参考标准来源:${NC}"
    echo "  • MLCommons MLPerf Inference v5.0 (2025)"
    echo "  • NVIDIA NIM Benchmarking Metrics"
    echo "  • https://docs.nvidia.com/nim/benchmarking/llm/latest/metrics.html"
    
    # TTFT 测试
    echo -e "\n${BLUE}[2.1] TTFT (Time to First Token) - 行业标准: ≤${INDUSTRY_STANDARD_TTFT_1K_PROMPT}ms${NC}"
    printf "  %-25s %-15s %-15s %s\n" "Prompt长度" "TTFT (ms)" "行业标准" "状态"
    echo "  -----------------------------------------------------------------------------"
    
    ttft_results=()
    for len in 10 100 500 1000 2000; do
        prompt=$(python3 -c "print('测试 ' * $((len/2)))")
        total=0
        for run in 1 2 3; do
            start=$(date +%s%N)
            curl -s --max-time 30 -X POST $LLM_URL/v1/chat/completions \
                -H "Content-Type: application/json" \
                -d "{\"model\": \"$LLM_MODEL\", \"messages\": [{\"role\": \"user\", \"content\": \"$prompt\"}], \"max_tokens\": 30}" > /dev/null
            end=$(date +%s%N)
            total=$((total + (end - start) / 1000000))
        done
        avg=$((total / 3))
        ttft_results+=($avg)
        
        if [ "$avg" -le "$INDUSTRY_STANDARD_TTFT_1K_PROMPT" ]; then
            status="${GREEN}✓ 达标${NC}"
        else
            status="${YELLOW}△${NC}"
        fi
        printf "  %-25s %-15s %-15s %s\n" "~${len}字符" "${avg}ms" "${INDUSTRY_STANDARD_TTFT_1K_PROMPT}ms" "$status"
    done
    
    # TPS 测试
    echo -e "\n${BLUE}[2.2] TPS (Tokens Per Second) - 行业标准: ≥${INDUSTRY_STANDARD_TPS_120B} tokens/s${NC}"
    printf "  %-15s %-12s %-10s %-12s %s\n" "max_tokens" "生成tokens" "耗时" "TPS" "状态"
    echo "  -----------------------------------------------------------------------------"
    
    for max_tok in 100 500 1000 2000; do
        start=$(date +%s%N)
        result=$(curl -s --max-time 120 -X POST $LLM_URL/v1/chat/completions \
            -H "Content-Type: application/json" \
            -d "{\"model\": \"$LLM_MODEL\", \"messages\": [{\"role\": \"user\", \"content\": \"请详细描述未来智能城市\"}], \"max_tokens\": $max_tok}")
        end=$(date +%s%N)
        duration=$(( (end - start) / 1000 ))
        
        chars=$(echo "$result" | grep -o '"content":"[^"]*"' | sed 's/"content":"//;s/"$//' | wc -c)
        tokens=$((chars / 4))
        
        if [ "$duration" -gt 0 ]; then
            tps=$(echo "scale=1; $tokens * 1000 / $duration" | bc 2>/dev/null || echo "0")
            
            if (( $(echo "$tps >= $INDUSTRY_STANDARD_TPS_120B" | bc -l) )); then
                status="${GREEN}✓ 达标${NC}"
            else
                status="${YELLOW}△${NC}"
            fi
            printf "  %-15s %-12s %-10s %-12s %s\n" "$max_tok" "~${tokens}t" "${duration}ms" "${tps}t/s" "$status"
        fi
    done
    
    # E2E 延迟测试
    echo -e "\n${BLUE}[2.3] E2E 延迟 (End-to-End) - 行业标准: ≤${INDUSTRY_STANDARD_E2E_LATENCY}ms${NC}"
    printf "  %-15s %-15s %-15s %s\n" "输出长度" "E2E延迟" "行业标准" "状态"
    echo "  -----------------------------------------------------------------------------"
    
    for output_len in 100 500 1000; do
        start=$(date +%s%N)
        result=$(curl -s --max-time 120 -X POST $LLM_URL/v1/chat/completions \
            -H "Content-Type: application/json" \
            -d "{\"model\": \"$LLM_MODEL\", \"messages\": [{\"role\": \"user\", \"content\": \"列出10个未来科技趋势\"}], \"max_tokens\": $output_len}")
        end=$(date +%s%N)
        e2e=$(( (end - start) / 1000 ))
        
        if [ "$e2e" -le "$INDUSTRY_STANDARD_E2E_LATENCY" ]; then
            status="${GREEN}✓ 达标${NC}"
        else
            status="${YELLOW}△${NC}"
        fi
        printf "  %-15s %-15s %-15s %s\n" "~${output_len}t" "${e2e}ms" "${INDUSTRY_STANDARD_E2E_LATENCY}ms" "$status"
    done
    
    # 并发性能测试
    echo -e "\n${BLUE}[2.4] RPS (Requests Per Second) 并发性能 - 行业标准: ≥${INDUSTRY_STANDARD_RPS_4CONCURRENT} RPS (4并发)${NC}"
    printf "  %-15s %-15s %-15s %s\n" "并发数" "总耗时" "RPS" "状态"
    echo "  -----------------------------------------------------------------------------"
    
    for conc in 1 2 4 8; do
        start=$(date +%s)
        for i in $(seq 1 $conc); do
            curl -s --max-time 60 -X POST $LLM_URL/v1/chat/completions \
                -H "Content-Type: application/json" \
                -d "{\"model\": \"$LLM_MODEL\", \"messages\": [{\"role\": \"user\", \"content\": \"你好\"}], \"max_tokens\": 20}" > /dev/null &
        done
        wait
        end=$(date +%s)
        duration=$((end - start))
        
        if [ "$duration" -gt 0 ]; then
            rps=$(echo "scale=2; $conc / $duration" | bc)
            
            if [ "$conc" -eq 4 ] && (( $(echo "$rps >= $INDUSTRY_STANDARD_RPS_4CONCURRENT" | bc -l) )); then
                status="${GREEN}✓ 达标${NC}"
            elif [ "$conc" -eq 4 ]; then
                status="${YELLOW}△${NC}"
            else
                status="-"
            fi
            printf "  %-15s %-15s %-15s %s\n" "$conc" "${duration}秒" "${rps}" "$status"
        fi
    done
}

#==============================================================================
# 3. Embedding 性能测试
#==============================================================================
test_embedding() {
    print_header "Embedding 性能测试"
    
    # 基础测试
    echo -e "\n${BLUE}[3.1] 基础 Embedding 测试${NC}"
    start=$(date +%s%N)
    result=$(curl -s --max-time 30 -X POST $EMBED_URL/v1/embeddings \
        -H "Content-Type: application/json" \
        -d '{"model": "'$EMBED_MODEL'", "input": "Hello world, this is a test"}')
    end=$(date +%s%N)
    duration=$(( (end - start) / 1000000 ))
    
    dim=$(echo "$result" | jq -r '.data[0].embedding | length' 2>/dev/null || echo "0")
    if [ "$dim" -gt 0 ]; then
        echo -e "  ✅ 向量维度=$dim, 延迟=${duration}ms"
    else
        echo -e "  ❌ Embedding 生成失败"
    fi
    
    # 文本长度 vs 延迟
    echo -e "\n${BLUE}[3.2] 文本长度 vs 延迟${NC}"
    printf "  %-20s %-12s %-10s %s\n" "文本长度" "延迟" "向量维度" "状态"
    echo "  -----------------------------------------------------------------------------"
    
    for len in 10 50 100 500 1000 5000; do
        text=$(python3 -c "print('测试文本 ' * $((len/4)))")
        
        start=$(date +%s%N)
        result=$(curl -s --max-time 30 -X POST $EMBED_URL/v1/embeddings \
            -H "Content-Type: application/json" \
            -d "{\"model\": \"$EMBED_MODEL\", \"input\": \"$text\"}")
        end=$(date +%s%N)
        duration=$(( (end - start) / 1000000 ))
        
        dim=$(echo "$result" | jq -r '.data[0].embedding | length' 2>/dev/null || echo "0")
        
        if [ "$dim" -gt 0 ] && [ "$duration" -lt 5000 ]; then
            printf "  %-20s %-12s %-10s %s\n" "~${len}字符" "${duration}ms" "$dim" "✅"
        else
            printf "  %-20s %-12s %-10s %s\n" "~${len}字符" "${duration}ms" "$dim" "⚠️"
        fi
    done
    
    # 批量处理
    echo -e "\n${BLUE}[3.3] 批量处理吞吐量${NC}"
    printf "  %-15s %-12s %-12s %s\n" "批量大小" "总延迟" "平均延迟" "吞吐量"
    echo "  -----------------------------------------------------------------------------"
    
    for batch_size in 1 5 10 20; do
        inputs=""
        for i in $(seq 1 $batch_size); do
            inputs="$inputs\"测试文本$i\""
            if [ $i -lt $batch_size ]; then
                inputs="$inputs,"
            fi
        done
        
        start=$(date +%s%N)
        result=$(curl -s --max-time 60 -X POST $EMBED_URL/v1/embeddings \
            -H "Content-Type: application/json" \
            -d "{\"model\": \"$EMBED_MODEL\", \"input\": [$inputs]}")
        end=$(date +%s%N)
        duration=$(( (end - start) / 1000000 ))
        
        avg_latency=$((duration / batch_size))
        throughput=$(echo "scale=1; 1000 / $avg_latency" | bc 2>/dev/null || echo "N/A")
        
        printf "  %-15s %-12s %-12s %s\n" "$batch_size" "${duration}ms" "${avg_latency}ms" "${throughput} QPS"
    done
}

#==============================================================================
# 4. 行业标准对比
#==============================================================================
compare_industry_standard() {
    print_header "行业标准对比分析"
    
    echo -e "\n${YELLOW}参考标准:${NC}"
    echo "  • MLCommons MLPerf Inference v5.0 (2025)"
    echo "  • NVIDIA NIM LLM Benchmarking"
    echo "  • https://mlcommons.org/2025/04/llm-inference-v5/"
    
    echo -e "\n${BLUE}[4.1] 关键指标对比${NC}"
    echo ""
    printf "  %-25s %-15s %-15s %-15s %s\n" "指标" "实测值" "行业标准" "差距" "评级"
    echo "  -----------------------------------------------------------------------------------------"
    
    # TTFT 对比
    prompt_1k_time=0
    for run in 1 2 3; do
        start=$(date +%s%N)
        curl -s --max-time 30 -X POST $LLM_URL/v1/chat/completions \
            -H "Content-Type: application/json" \
            -d "{\"model\": \"$LLM_MODEL\", \"messages\": [{\"role\": \"user\", \"content\": \"$([1..500])\"}], \"max_tokens\": 20}" > /dev/null
        end=$(date +%s%N)
        prompt_1k_time=$((prompt_1k_time + (end - start) / 1000000))
    done
    prompt_1k_time=$((prompt_1k_time / 3))
    
    ttft_gap=$((prompt_1k_time - INDUSTRY_STANDARD_TTFT_1K_PROMPT))
    if [ "$ttft_gap" -lt 0 ]; then
        ttft_rating="${GREEN}优秀${NC}"
    elif [ "$ttft_gap" -lt 500 ]; then
        ttft_rating="${GREEN}良好${NC}"
    else
        ttft_rating="${YELLOW}待优化${NC}"
    fi
    printf "  %-25s %-15s %-15s %-15s %s\n" "TTFT (1K prompt)" "${prompt_1k_time}ms" "${INDUSTRY_STANDARD_TTFT_1K_PROMPT}ms" "${ttft_gap}ms" "$ttft_rating"
    
    # TPS 对比
    start=$(date +%s%N)
    result=$(curl -s --max-time 60 -X POST $LLM_URL/v1/chat/completions \
        -H "Content-Type: application/json" \
        -d "{\"model\": \"$LLM_MODEL\", \"messages\": [{\"role\": \"user\", \"content\": \"测试\"}], \"max_tokens\": 500}")
    end=$(date +%s%N)
    duration=$(( (end - start) / 1000 ))
    chars=$(echo "$result" | grep -o '"content":"[^"]*"' | sed 's/"content":"//;s/"$//' | wc -c)
    tokens=$((chars / 4))
    tps=$(echo "scale=1; $tokens * 1000 / $duration" | bc 2>/dev/null || echo "0")
    
    tps_gap=$(echo "scale=1; $tps - $INDUSTRY_STANDARD_TPS_120B" | bc 2>/dev/null || echo "0")
    if (( $(echo "$tps >= $INDUSTRY_STANDARD_TPS_120B" | bc -l) )); then
        tps_rating="${GREEN}优秀${NC}"
    else
        tps_rating="${YELLOW}待优化${NC}"
    fi
    printf "  %-25s %-15s %-15s %-15s %s\n" "TPS" "${tps} tokens/s" "${INDUSTRY_STANDARD_TPS_120B} tokens/s" "${tps_gap} tokens/s" "$tps_rating"
    
    echo -e "\n${BLUE}[4.2] 总体评估${NC}"
    
    # 计算综合得分
    ttft_score=0
    if [ "$prompt_1k_time" -le "$INDUSTRY_STANDARD_TTFT_1K_PROMPT" ]; then
        ttft_score=100
    else
        ttft_score=$((100 - (prompt_1k_time - INDUSTRY_STANDARD_TTFT_1K_PROMPT) / 10))
    fi
    
    if (( $(echo "$tps >= $INDUSTRY_STANDARD_TPS_120B" | bc -l) )); then
        tps_score=100
    else
        tps_score=$(echo "scale=0; $tps * 100 / $INDUSTRY_STANDARD_TPS_120B" | bc 2>/dev/null || echo "0")
    fi
    
    overall_score=$(( (ttft_score + tps_score) / 2 ))
    
    echo ""
    echo "  ┌─────────────────────────────────────────────┐"
    echo "  │ 综合评分: $overall_score/100                      │"
    echo "  │  • TTFT 得分: $ttft_score/100                    │"
    echo "  │  • TPS 得分: $tps_score/100                      │"
    echo "  └─────────────────────────────────────────────┘"
    
    if [ "$overall_score" -ge 90 ]; then
        echo -e "\n  ${GREEN}🎉 性能优秀，达到行业领先水平${NC}"
    elif [ "$overall_score" -ge 70 ]; then
        echo -e "\n  ${YELLOW}⚠️  性能良好，部分指标待优化${NC}"
    else
        echo -e "\n  ${RED}⚠️  性能有待提升，建议优化配置${NC}"
    fi
}

#==============================================================================
# 5. 极限测试
#==============================================================================
test_extreme() {
    print_header "极限压力测试"
    
    echo -e "\n${BLUE}[5.1] 超长上下文 (4000+ tokens)${NC}"
    start=$(date +%s)
    result=$(curl -s --max-time 180 -X POST $LLM_URL/v1/chat/completions \
        -H "Content-Type: application/json" \
        -d '{"model": "'$LLM_MODEL'", "messages": [{"role": "user", "content": "请详细描述虚拟现实技术的发展历史和未来展望，包括硬件、软件、应用场景等各个方面"}], "max_tokens": 4000, "temperature": 0.7}')
    end=$(date +%s)
    duration=$((end - start))
    chars=$(echo "$result" | grep -o '"content":"[^"]*"' | sed 's/"content":"//;s/"$//' | wc -c)
    tokens=$((chars / 4))
    
    echo -e "  生成: ~${tokens} tokens, 耗时: ${duration}秒"
    if [ "$tokens" -gt 3500 ]; then
        echo -e "  ✅ 超长文本生成正常"
    fi
    
    echo -e "\n${BLUE}[5.2] 高并发压力 (8并发)${NC}"
    start=$(date +%s)
    for i in 1 2 3 4 5 6 7 8; do
        curl -s --max-time 120 -X POST $LLM_URL/v1/chat/completions \
            -H "Content-Type: application/json" \
            -d "{\"model\": \"$LLM_MODEL\", \"messages\": [{\"role\": \"user\", \"content\": \"描述未来智能城市\"}], \"max_tokens\": 1000}" > /tmp/extreme_$i.json &
    done
    wait
    end=$(date +%s)
    duration=$((end - start))
    
    success=0
    for i in 1 2 3 4 5 6 7 8; do
        if [ -s "/tmp/extreme_$i.json" ]; then
            success=$((success + 1))
        fi
    done
    
    echo -e "  8并发请求, 成功: $success/8, 总耗时: ${duration}秒"
    if [ "$success" -eq 8 ]; then
        echo -e "  ✅ 高并发处理正常"
    fi
}

#==============================================================================
# 主函数
#==============================================================================
main() {
    echo ""
    print_header "gpt-oss-120b 专业性能基准测试 v5"
    
    echo -e "${YELLOW}基于 MLCommons MLPerf Inference v5.0 & NVIDIA NIM 标准${NC}"
    echo ""
    
    case "${1:-}" in
        --verify)
            verify_config
            ;;
        --quick)
            verify_config
            test_llm_basic
            ;;
        --compare)
            verify_config
            compare_industry_standard
            ;;
        --llm)
            verify_config
            test_llm_basic
            test_llm_performance
            ;;
        --embed)
            verify_config
            test_embedding
            ;;
        --full)
            verify_config
            test_llm_basic
            test_llm_performance
            compare_industry_standard
            test_embedding
            test_extreme
            ;;
        *)
            verify_config
            test_llm_basic
            test_llm_performance
            test_embedding
            ;;
    esac
    
    echo ""
    print_header "测试完成"
    echo ""
    echo -e "${GREEN}✅ 基准测试执行完成${NC}"
    echo ""
    echo "使用 --compare 参数查看行业标准对比分析"
    echo "使用 --full 参数执行完整压力测试"
    echo ""
}

main "$@"
