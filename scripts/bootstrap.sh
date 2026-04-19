#!/usr/bin/env bash
# bootstrap.sh — WSL/Linux 환경 초기 설정
# 사용: bash scripts/bootstrap.sh

set -euo pipefail

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
GRAY='\033[0;37m'
RESET='\033[0m'

echo ""
echo -e "${CYAN}=== AI 비서 프로젝트 부트스트랩 (WSL) ===${RESET}"
echo ""

# 1. Open-LLM-VTuber clone
echo -e "${CYAN}[1/4] Open-LLM-VTuber clone 확인...${RESET}"
if [ ! -d "upstream/Open-LLM-VTuber/.git" ]; then
    if [ -d "upstream/Open-LLM-VTuber" ]; then
        rm -rf upstream/Open-LLM-VTuber
    fi
    git clone https://github.com/Open-LLM-VTuber/Open-LLM-VTuber.git upstream/Open-LLM-VTuber
    echo -e "  ${GREEN}→ upstream/Open-LLM-VTuber 에 clone 완료${RESET}"
else
    echo -e "  ${GRAY}upstream/Open-LLM-VTuber 이미 존재 — 건너뜀${RESET}"
fi
echo ""

# 2. Ollama 모델 확인·다운로드
echo -e "${CYAN}[2/4] Ollama 모델 확인·다운로드...${RESET}"
if ! command -v ollama &>/dev/null; then
    echo -e "  ${YELLOW}경고: ollama 명령을 찾을 수 없습니다. Windows 측 Ollama가 실행 중인지 확인하세요.${RESET}"
    echo -e "  ${YELLOW}모델 다운로드를 건너뜁니다. Windows PowerShell에서 직접 실행하세요:${RESET}"
    echo -e "  ${YELLOW}  ollama pull gemma4:e4b${RESET}"
    echo -e "  ${YELLOW}  ollama pull bge-m3${RESET}"
else
    OLLAMA_MODELS=$(ollama list 2>&1 || true)

    if echo "$OLLAMA_MODELS" | grep -q "gemma4"; then
        echo -e "  ${GRAY}gemma4 이미 존재 — 건너뜀${RESET}"
    else
        echo -e "  ${YELLOW}gemma4:e4b 다운로드 중 (약 3~5GB)...${RESET}"
        ollama pull gemma4:e4b
    fi

    if echo "$OLLAMA_MODELS" | grep -q "bge-m3"; then
        echo -e "  ${GRAY}bge-m3 이미 존재 — 건너뜀${RESET}"
    else
        echo -e "  ${YELLOW}bge-m3 임베딩 모델 다운로드 중...${RESET}"
        ollama pull bge-m3
    fi
fi
echo ""

# 3. Python 가상환경 (uv, Linux용 .venv)
echo -e "${CYAN}[3/4] Python 가상환경 생성...${RESET}"
# Windows에서 만들어진 .venv(Scripts/ 디렉토리 존재)는 WSL에서 사용 불가 — 재생성
if [ -d ".venv/Scripts" ]; then
    echo -e "  ${YELLOW}Windows용 .venv 감지 — WSL용으로 재생성합니다${RESET}"
    rm -rf .venv
fi

if [ ! -d ".venv" ]; then
    uv venv --python 3.11
    echo -e "  ${GREEN}→ .venv 생성 완료${RESET}"
else
    echo -e "  ${GRAY}.venv 이미 존재 — 건너뜀${RESET}"
fi
echo ""

# 4. pyproject.toml 및 개발 도구 설치
echo -e "${CYAN}[4/4] pyproject.toml 확인 및 개발 도구 설치...${RESET}"
if [ ! -f "pyproject.toml" ]; then
cat > pyproject.toml << 'EOF'
[project]
name = "ai-assistant"
version = "0.0.1"
description = "Offline multimodal AI assistant for corporate intranet"
requires-python = ">=3.11"
dependencies = []

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.mypy]
python_version = "3.11"
strict = true

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
EOF
    echo -e "  ${GREEN}→ pyproject.toml 생성${RESET}"
else
    echo -e "  ${GRAY}pyproject.toml 이미 존재 — 건너뜀${RESET}"
fi

mkdir -p src tests

# shellcheck disable=SC1091
source .venv/bin/activate
uv pip install ruff mypy pytest pytest-cov
deactivate
echo ""

echo -e "${GREEN}========================================${RESET}"
echo -e "${GREEN}부트스트랩 완료${RESET}"
echo -e "${GREEN}========================================${RESET}"
echo ""
echo -e "${CYAN}다음 단계:${RESET}"
echo "  1. 이 폴더에서 Claude Code 실행: claude"
echo "  2. prompts/00_kickoff.md 의 프롬프트를 복사해 Claude Code에 붙여넣기"
echo ""
