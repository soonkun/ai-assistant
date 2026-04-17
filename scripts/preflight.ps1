# preflight.ps1 — 환경 점검
# 사용: PowerShell에서 .\scripts\preflight.ps1

Write-Host "`n=== AI 비서 프로젝트 환경 점검 ===" -ForegroundColor Cyan
Write-Host ""

$checks = @()

function Check-Cmd($name, $cmd, $minVersion, $installHint) {
    $ok = $false
    $version = ""
    try {
        $version = (Invoke-Expression $cmd 2>&1 | Out-String).Trim()
        if ($version -and $LASTEXITCODE -eq 0) { $ok = $true }
    } catch { $ok = $false }
    
    if ($ok) {
        Write-Host "[OK]  $name : $version" -ForegroundColor Green
    } else {
        Write-Host "[MISS] $name : 설치 안 됨 또는 PATH 미등록" -ForegroundColor Red
        Write-Host "       → $installHint" -ForegroundColor Yellow
    }
    return $ok
}

$ok_git    = Check-Cmd "Git"     "git --version"      ""   "https://git-scm.com/download/win"
$ok_py     = Check-Cmd "Python"  "python --version"   "3.11" "https://www.python.org/downloads/ (3.11 이상, 'Add to PATH' 체크)"
$ok_node   = Check-Cmd "Node.js" "node --version"     "20"   "https://nodejs.org/ (20 LTS 이상)"
$ok_uv     = Check-Cmd "uv"      "uv --version"       ""   "pip install uv (또는 https://docs.astral.sh/uv/)"
$ok_ffmpeg = Check-Cmd "ffmpeg"  "ffmpeg -version"    ""   "https://www.gyan.dev/ffmpeg/builds/ 에서 다운로드 후 PATH 등록"
$ok_ollama = Check-Cmd "Ollama"  "ollama --version"   ""   "https://ollama.com/download/windows"
$ok_claude = Check-Cmd "Claude Code" "claude --version" "" "npm install -g @anthropic-ai/claude-code"

Write-Host ""
Write-Host "=== Ollama 모델 확인 ===" -ForegroundColor Cyan
if ($ok_ollama) {
    $models = (ollama list 2>&1 | Out-String)
    if ($models -match "gemma4") {
        Write-Host "[OK]  gemma4 모델 발견" -ForegroundColor Green
    } else {
        Write-Host "[MISS] gemma4:e4b 미설치 → ollama pull gemma4:e4b" -ForegroundColor Yellow
    }
    if ($models -match "bge-m3") {
        Write-Host "[OK]  bge-m3 임베딩 모델 발견" -ForegroundColor Green
    } else {
        Write-Host "[INFO] bge-m3 임베딩 모델 없음 → ollama pull bge-m3 (RAG 단계에서 필요)" -ForegroundColor Gray
    }
}

Write-Host ""
Write-Host "=== 디스크 공간 확인 ===" -ForegroundColor Cyan
$drive = (Get-PSDrive C)
$freeGB = [math]::Round($drive.Free / 1GB, 1)
if ($freeGB -lt 30) {
    Write-Host "[WARN] C: 여유 공간 $freeGB GB (모델·번들 포함해 30GB 이상 권장)" -ForegroundColor Yellow
} else {
    Write-Host "[OK]  C: 여유 공간 $freeGB GB" -ForegroundColor Green
}

Write-Host ""
Write-Host "=== RAM 확인 ===" -ForegroundColor Cyan
$ramGB = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB, 1)
if ($ramGB -lt 16) {
    Write-Host "[WARN] 전체 RAM $ramGB GB — Gemma 4 E4B는 최소 16GB 권장" -ForegroundColor Yellow
} else {
    Write-Host "[OK]  RAM $ramGB GB" -ForegroundColor Green
}

Write-Host ""
if ($ok_git -and $ok_py -and $ok_node -and $ok_uv -and $ok_ffmpeg -and $ok_ollama -and $ok_claude) {
    Write-Host "전제 조건 모두 충족. bootstrap.ps1 실행 가능." -ForegroundColor Green
} else {
    Write-Host "누락 항목을 먼저 설치한 뒤 이 스크립트를 다시 실행하세요." -ForegroundColor Red
}
Write-Host ""
