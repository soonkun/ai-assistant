# bootstrap.ps1 — 초기 환경 설정
# 사용: PowerShell에서 .\scripts\bootstrap.ps1

$ErrorActionPreference = "Stop"

Write-Host "`n=== AI 비서 프로젝트 부트스트랩 ===" -ForegroundColor Cyan
Write-Host ""

# 1. Open-LLM-VTuber clone
if (-not (Test-Path "upstream\Open-LLM-VTuber\.git")) {
    Write-Host "[1/5] Open-LLM-VTuber clone 중..." -ForegroundColor Cyan
    if (Test-Path "upstream\Open-LLM-VTuber") {
        Remove-Item "upstream\Open-LLM-VTuber" -Recurse -Force
    }
    git clone https://github.com/Open-LLM-VTuber/Open-LLM-VTuber.git upstream\Open-LLM-VTuber
    Write-Host "  → upstream\Open-LLM-VTuber 에 clone 완료" -ForegroundColor Green
} else {
    Write-Host "[1/5] upstream\Open-LLM-VTuber 이미 존재 — 건너뜀" -ForegroundColor Gray
}
Write-Host ""

# 2. Gemma 4 E4B 모델 풀
Write-Host "[2/5] Ollama 모델 확인·다운로드..." -ForegroundColor Cyan
$models = (ollama list 2>&1 | Out-String)
if ($models -notmatch "gemma4") {
    Write-Host "  gemma4:e4b 다운로드 중 (약 3~5GB)..." -ForegroundColor Yellow
    ollama pull gemma4:e4b
} else {
    Write-Host "  gemma4 이미 존재 — 건너뜀" -ForegroundColor Gray
}
if ($models -notmatch "bge-m3") {
    Write-Host "  bge-m3 임베딩 모델 다운로드 중..." -ForegroundColor Yellow
    ollama pull bge-m3
} else {
    Write-Host "  bge-m3 이미 존재 — 건너뜀" -ForegroundColor Gray
}
Write-Host ""

# 3. Python 가상환경
Write-Host "[3/5] Python 가상환경 생성..." -ForegroundColor Cyan
if (-not (Test-Path ".venv")) {
    uv venv --python 3.11
    Write-Host "  → .venv 생성 완료" -ForegroundColor Green
} else {
    Write-Host "  .venv 이미 존재 — 건너뜀" -ForegroundColor Gray
}
Write-Host ""

# 4. 프로젝트 메타데이터 초기화
Write-Host "[4/5] pyproject.toml 초기화..." -ForegroundColor Cyan
if (-not (Test-Path "pyproject.toml")) {
@"
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
"@ | Set-Content -Path "pyproject.toml" -Encoding UTF8
    Write-Host "  → pyproject.toml 생성" -ForegroundColor Green
} else {
    Write-Host "  pyproject.toml 이미 존재 — 건너뜀" -ForegroundColor Gray
}
if (-not (Test-Path "src")) { New-Item -ItemType Directory -Path "src" | Out-Null }
if (-not (Test-Path "tests")) { New-Item -ItemType Directory -Path "tests" | Out-Null }

# 개발 도구 설치
.\.venv\Scripts\Activate.ps1
uv pip install ruff mypy pytest pytest-cov
deactivate
Write-Host ""

# 5. git 초기화
Write-Host "[5/5] git 초기화..." -ForegroundColor Cyan
if (-not (Test-Path ".git")) {
    git init | Out-Null
    git add README.md REQUIREMENTS.md CLAUDE.md PROJECT_PLAN.md .gitignore .claude/ prompts/ docs/ scripts/ specs/.gitkeep reviews/.gitkeep upstream/.gitkeep assets/ pyproject.toml | Out-Null
    git commit -m "chore: initial starter kit" | Out-Null
    Write-Host "  → git 저장소 초기화·최초 커밋" -ForegroundColor Green
} else {
    Write-Host "  .git 이미 존재 — 건너뜀" -ForegroundColor Gray
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "부트스트랩 완료" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "다음 단계:" -ForegroundColor Cyan
Write-Host "  1. 이 폴더에서 Claude Code 실행: claude"
Write-Host "  2. prompts/00_kickoff.md 의 프롬프트를 복사해 Claude Code에 붙여넣기"
Write-Host ""
