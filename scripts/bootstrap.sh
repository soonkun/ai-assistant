#!/usr/bin/env bash
# bootstrap.sh — macOS / Linux 초기 환경 설정
# 사용: bash scripts/bootstrap.sh

set -euo pipefail

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
GRAY='\033[0;37m'
RESET='\033[0m'

OS="$(uname)"
ARCH="$(uname -m)"

echo ""
echo -e "${CYAN}=== AI 비서 프로젝트 부트스트랩 (${OS} ${ARCH}) ===${RESET}"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# 1. 필수 도구 설치 (Homebrew / apt)
# ─────────────────────────────────────────────────────────────────────────────
echo -e "${CYAN}[1/5] 필수 도구 확인·설치 (ffmpeg, node)...${RESET}"

install_brew_pkg() {
    local pkg="$1"
    if command -v "$pkg" &>/dev/null; then
        echo -e "  ${GRAY}${pkg} 이미 설치됨 — 건너뜀${RESET}"
    else
        echo -e "  ${YELLOW}${pkg} 설치 중...${RESET}"
        brew install "$pkg"
        echo -e "  ${GREEN}→ ${pkg} 설치 완료${RESET}"
    fi
}

install_apt_pkg() {
    local pkg="$1"
    local cmd="${2:-$1}"
    if command -v "$cmd" &>/dev/null; then
        echo -e "  ${GRAY}${pkg} 이미 설치됨 — 건너뜀${RESET}"
    else
        echo -e "  ${YELLOW}${pkg} 설치 중...${RESET}"
        sudo apt-get update -qq
        sudo apt-get install -y "$pkg"
        echo -e "  ${GREEN}→ ${pkg} 설치 완료${RESET}"
    fi
}

if [[ "$OS" == "Darwin" ]]; then
    # macOS: Homebrew 필요
    if ! command -v brew &>/dev/null; then
        echo -e "${YELLOW}Homebrew가 설치되지 않았습니다. 먼저 Homebrew를 설치하세요:${RESET}"
        echo -e "${YELLOW}  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\"${RESET}"
        echo -e "${YELLOW}설치 후 이 스크립트를 다시 실행하세요.${RESET}"
        exit 1
    fi
    install_brew_pkg ffmpeg
    install_brew_pkg node
elif [[ "$OS" == "Linux" ]]; then
    if command -v apt-get &>/dev/null; then
        install_apt_pkg ffmpeg
        install_apt_pkg nodejs node
    else
        echo -e "${YELLOW}apt-get을 찾을 수 없습니다. ffmpeg 및 Node.js를 수동으로 설치하세요.${RESET}"
    fi
else
    echo -e "${YELLOW}알 수 없는 OS: ${OS}. 필수 도구를 수동으로 설치하세요.${RESET}"
fi
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# 2. Python 버전 체크 (3.11+)
# ─────────────────────────────────────────────────────────────────────────────
echo -e "${CYAN}[2/5] Python 버전 확인...${RESET}"
if ! python3 --version 2>&1 | grep -qE "Python 3\.(1[1-9]|[2-9][0-9])"; then
    py_ver=$(python3 --version 2>&1 || echo "미설치")
    echo -e "${YELLOW}Python 3.11+ 필요. 현재: ${py_ver}${RESET}"
    if [[ "$OS" == "Darwin" ]]; then
        echo -e "${YELLOW}  brew install python@3.11 또는 pyenv 사용을 권장합니다.${RESET}"
    else
        echo -e "${YELLOW}  sudo apt install python3.11 또는 pyenv 사용을 권장합니다.${RESET}"
    fi
    exit 1
fi
echo -e "  ${GREEN}Python $(python3 --version 2>&1) — OK${RESET}"
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# 3. uv 설치
# ─────────────────────────────────────────────────────────────────────────────
echo -e "${CYAN}[3/5] uv 설치 확인...${RESET}"
if ! command -v uv &>/dev/null; then
    echo -e "  ${YELLOW}uv 설치 중 (pip install uv)...${RESET}"
    python3 -m pip install --quiet uv
    echo -e "  ${GREEN}→ uv 설치 완료${RESET}"
else
    echo -e "  ${GRAY}uv 이미 설치됨 ($(uv --version 2>&1 | head -1)) — 건너뜀${RESET}"
fi
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# 4. Python 가상환경 생성 및 개발 도구 설치
# ─────────────────────────────────────────────────────────────────────────────
echo -e "${CYAN}[4/5] Python 가상환경 생성...${RESET}"

# macOS/Linux의 경우 OS별 .venv는 그대로 재사용 가능; 단 Windows에서 복사된 .venv는 제거
if [ -d ".venv/Scripts" ]; then
    echo -e "  ${YELLOW}Windows용 .venv 감지 — 재생성합니다${RESET}"
    rm -rf .venv
fi

if [ ! -d ".venv" ]; then
    uv venv --python 3.11
    echo -e "  ${GREEN}→ .venv 생성 완료${RESET}"
else
    echo -e "  ${GRAY}.venv 이미 존재 — 건너뜀${RESET}"
fi

# shellcheck disable=SC1091
source .venv/bin/activate
uv pip install --quiet ruff mypy pytest pytest-cov
deactivate
echo ""

# ─────────────────────────────────────────────────────────────────────────────
# 5. Ollama 설치 안내
# ─────────────────────────────────────────────────────────────────────────────
echo -e "${CYAN}[5/5] Ollama 확인...${RESET}"
if command -v ollama &>/dev/null; then
    echo -e "  ${GRAY}Ollama 이미 설치됨 ($(ollama --version 2>&1 | head -1)) — 건너뜀${RESET}"
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
else
    echo -e "  ${YELLOW}Ollama 미설치. 수동 설치 필요:${RESET}"
    if [[ "$OS" == "Darwin" ]]; then
        echo -e "  ${YELLOW}  brew install ollama${RESET}"
        echo -e "  ${YELLOW}  또는 https://ollama.com/download/mac${RESET}"
    else
        echo -e "  ${YELLOW}  curl -fsSL https://ollama.com/install.sh | sh${RESET}"
        echo -e "  ${YELLOW}  (사내 오프라인 환경: 수동 rpm/deb 패키지 설치)${RESET}"
    fi
    echo -e "  ${YELLOW}설치 후: ollama pull gemma4:e4b && ollama pull bge-m3${RESET}"
fi
echo ""

mkdir -p src tests

echo -e "${GREEN}========================================${RESET}"
echo -e "${GREEN}부트스트랩 완료${RESET}"
echo -e "${GREEN}========================================${RESET}"
echo ""
echo -e "${CYAN}다음 단계:${RESET}"
echo "  1. 이 폴더에서 Claude Code 실행: claude"
echo "  2. prompts/00_kickoff.md 의 프롬프트를 복사해 Claude Code에 붙여넣기"
echo ""
