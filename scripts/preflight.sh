#!/usr/bin/env bash
# preflight.sh — 환경 점검 (macOS / Linux)
# 사용: bash scripts/preflight.sh

set -euo pipefail

CYAN='\033[0;36m'
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
GRAY='\033[0;37m'
RESET='\033[0m'

echo ""
echo -e "${CYAN}=== AI 비서 프로젝트 환경 점검 ===${RESET}"
echo ""

ok_all=true

check_cmd() {
    local name="$1"
    local cmd="$2"
    local install_hint="$3"
    local result

    if result=$(eval "$cmd" 2>&1); then
        echo -e "${GREEN}[OK]  ${name} : ${result}${RESET}"
        return 0
    else
        echo -e "${RED}[MISS] ${name} : 설치 안 됨 또는 PATH 미등록${RESET}"
        echo -e "${YELLOW}       → ${install_hint}${RESET}"
        ok_all=false
        return 1
    fi
}

# Git
check_cmd "Git" \
    "git --version | head -1" \
    "https://git-scm.com/download/ 또는 brew install git"

# Python 3.11+
if python3 --version 2>&1 | grep -qE "Python 3\.(1[1-9]|[2-9][0-9])"; then
    py_ver=$(python3 --version 2>&1)
    echo -e "${GREEN}[OK]  Python : ${py_ver}${RESET}"
else
    echo -e "${RED}[MISS] Python 3.11+ : 현재 버전 불충족${RESET}"
    echo -e "${YELLOW}       → https://www.python.org/downloads/ 또는 brew install python@3.11${RESET}"
    ok_all=false
fi

# Node.js
check_cmd "Node.js" \
    "node --version" \
    "https://nodejs.org/ (20 LTS) 또는 brew install node"

# uv
check_cmd "uv" \
    "uv --version | head -1" \
    "pip install uv 또는 curl -Lsf https://astral.sh/uv/install.sh | sh (사내망: pip 사용)"

# ffmpeg
check_cmd "ffmpeg" \
    "ffmpeg -version 2>&1 | head -1" \
    "brew install ffmpeg (macOS) 또는 sudo apt install ffmpeg (Linux)"

# Claude Code
check_cmd "Claude Code" \
    "claude --version 2>&1 | head -1" \
    "npm install -g @anthropic-ai/claude-code"

echo ""
echo -e "${CYAN}=== Ollama 확인 ===${RESET}"
if command -v ollama &>/dev/null; then
    OLLAMA_VER=$(ollama --version 2>&1 | head -1)
    echo -e "${GREEN}[OK]  Ollama : ${OLLAMA_VER}${RESET}"
    OLLAMA_MODELS=$(ollama list 2>&1 || true)
    if echo "$OLLAMA_MODELS" | grep -q "gemma4"; then
        echo -e "${GREEN}[OK]  gemma4 모델 발견${RESET}"
    else
        echo -e "${YELLOW}[MISS] gemma4:e4b 미설치 → ollama pull gemma4:e4b${RESET}"
    fi
    if echo "$OLLAMA_MODELS" | grep -q "bge-m3"; then
        echo -e "${GREEN}[OK]  bge-m3 임베딩 모델 발견${RESET}"
    else
        echo -e "${GRAY}[INFO] bge-m3 임베딩 모델 없음 → ollama pull bge-m3 (RAG 단계에서 필요)${RESET}"
    fi
else
    echo -e "${YELLOW}[MISS] Ollama 미설치${RESET}"
    echo -e "${YELLOW}       → macOS: brew install ollama 또는 https://ollama.com/download/mac${RESET}"
    echo -e "${YELLOW}       → Linux: curl -fsSL https://ollama.com/install.sh | sh (사내망: 수동 설치)${RESET}"
    ok_all=false
fi

echo ""
echo -e "${CYAN}=== 디스크 공간 확인 ===${RESET}"
if [[ "$(uname)" == "Darwin" ]]; then
    free_bytes=$(df -k . | tail -1 | awk '{print $4}')
    free_gb=$(echo "scale=1; $free_bytes / 1048576" | bc)
else
    free_bytes=$(df -k . | tail -1 | awk '{print $4}')
    free_gb=$(echo "scale=1; $free_bytes / 1048576" | bc)
fi
if (( $(echo "$free_gb < 30" | bc -l) )); then
    echo -e "${YELLOW}[WARN] 여유 공간 ${free_gb}GB (모델·번들 포함 30GB 이상 권장)${RESET}"
else
    echo -e "${GREEN}[OK]  여유 공간 ${free_gb}GB${RESET}"
fi

echo ""
echo -e "${CYAN}=== RAM 확인 ===${RESET}"
if [[ "$(uname)" == "Darwin" ]]; then
    ram_bytes=$(sysctl -n hw.memsize)
    ram_gb=$(echo "scale=1; $ram_bytes / 1073741824" | bc)
else
    ram_kb=$(grep MemTotal /proc/meminfo | awk '{print $2}')
    ram_gb=$(echo "scale=1; $ram_kb / 1048576" | bc)
fi
if (( $(echo "$ram_gb < 16" | bc -l) )); then
    echo -e "${YELLOW}[WARN] 전체 RAM ${ram_gb}GB — Gemma 4 E4B는 최소 16GB 권장${RESET}"
else
    echo -e "${GREEN}[OK]  RAM ${ram_gb}GB${RESET}"
fi

echo ""
if $ok_all; then
    echo -e "${GREEN}전제 조건 모두 충족. bootstrap.sh 실행 가능.${RESET}"
else
    echo -e "${RED}누락 항목을 먼저 설치한 뒤 이 스크립트를 다시 실행하세요.${RESET}"
fi
echo ""
