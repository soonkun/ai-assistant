"""
Spike: LibreOffice headless HWPX→PDF 변환 + PyMuPDF 파싱 검증
Usage: ~/venvs/ai-assistant/bin/python scripts/spike_hwpx.py
"""

import logging
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
SAMPLE_DIR = PROJECT_ROOT / "tests" / "fixtures" / "hwpx"
OUTPUT_DIR = PROJECT_ROOT / "docs" / "research"
RESULT_FILE = OUTPUT_DIR / "hwpx_spike.md"

# ---------------------------------------------------------------------------
# 샘플 HWPX 파일 3종 생성 (ZIP + XML 구조)
# ---------------------------------------------------------------------------


def _make_hwpx(path: Path, title: str, sections: list[dict[str, str]]) -> None:
    """최소 구조의 HWPX 파일 생성."""
    # HWPX는 ZIP 컨테이너 + XML
    # 실제 포맷 단순화: Contents/section0.xml 에 본문 텍스트 삽입
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        # mimetype
        zf.writestr("mimetype", "application/x-hwp+zip")

        # version.xml
        zf.writestr(
            "version.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<hh:HWPFDocumentVersion xmlns:hh="urn:HWPFDocumentVersion"'
            ' AppVersion="10.0.0.0" ProductVersion="10.0.0.0"/>',
        )

        # Contents/section0.xml — 본문
        body_lines = []
        for sec in sections:
            body_lines.append(f"<hp:p><hp:run><hp:t>{sec['text']}</hp:t></hp:run></hp:p>")
        body_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<hh:sec xmlns:hh="urn:oasis:names:tc:opendocument:xmlns:text:1.0"'
            ' xmlns:hp="urn:hancom:names:tc:opendocument:xmlns:paragraph:1.0">'
            + "".join(body_lines)
            + "</hh:sec>"
        )
        zf.writestr("Contents/section0.xml", body_xml)

        # content.hpf — 패키지 메타
        hpf = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<rootfiles>"
            '<rootfile full-path="Contents/section0.xml"'
            ' media-type="application/x-hwp-v5+xml"/>'
            "</rootfiles>"
        )
        zf.writestr("content.hpf", hpf)


SAMPLES: list[dict[str, Any]] = [
    {
        "name": "sample1_meeting.hwpx",
        "title": "주간 회의록",
        "sections": [
            {"text": "일시: 2026년 4월 18일 오전 10시"},
            {"text": "참석자: 김철수, 이영희, 박민준"},
            {"text": "안건 1: 1분기 실적 검토"},
            {"text": "결론: 목표 대비 105% 달성. 2분기 목표 상향 조정."},
        ],
    },
    {
        "name": "sample2_policy.hwpx",
        "title": "보안 정책 문서",
        "sections": [
            {"text": "제1조 목적: 본 정책은 사내 정보 보안을 강화하기 위함이다."},
            {"text": "제2조 적용 범위: 전 임직원 및 협력업체 직원에게 적용된다."},
            {"text": "제3조 비밀번호 정책: 비밀번호는 90일마다 변경해야 한다."},
        ],
    },
    {
        "name": "sample3_report.hwpx",
        "title": "월간 보고서",
        "sections": [
            {"text": "2026년 3월 월간 실적 보고서"},
            {"text": "매출: 12억 3천만 원 (전월 대비 +8%)"},
            {"text": "비용: 9억 1천만 원 (전월 대비 +3%)"},
            {"text": "순이익: 3억 2천만 원"},
            {"text": "특이사항: 신규 고객사 3곳 계약 체결"},
        ],
    },
]


def create_samples() -> list[Path]:
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for s in SAMPLES:
        p = SAMPLE_DIR / s["name"]
        _make_hwpx(p, s["title"], s["sections"])
        logger.info(f"샘플 생성: {p.name} ({p.stat().st_size} bytes)")
        paths.append(p)
    return paths


# ---------------------------------------------------------------------------
# LibreOffice headless 변환
# ---------------------------------------------------------------------------


def convert_to_pdf(hwpx_path: Path, out_dir: Path) -> Path | None:
    """HWPX → PDF 변환. 성공 시 PDF 경로 반환."""
    cmd = [
        "soffice",
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        str(out_dir),
        str(hwpx_path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            logger.error(f"변환 실패: {result.stderr.strip()}")
            return None
        pdf_path = out_dir / (hwpx_path.stem + ".pdf")
        if pdf_path.exists():
            logger.info(f"변환 성공: {pdf_path.name} ({pdf_path.stat().st_size} bytes)")
            return pdf_path
        logger.error(f"PDF 파일 미생성: {pdf_path}")
        return None
    except subprocess.TimeoutExpired:
        logger.error("변환 타임아웃 (60s)")
        return None
    except FileNotFoundError:
        logger.error("soffice 명령을 찾을 수 없음")
        return None


# ---------------------------------------------------------------------------
# PyMuPDF 파싱
# ---------------------------------------------------------------------------


def parse_pdf(pdf_path: Path) -> dict[str, Any]:
    """PDF에서 텍스트·페이지 수·메타데이터 추출."""
    import fitz  # PyMuPDF

    doc = fitz.open(str(pdf_path))
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text().strip()
        blocks = page.get_text("blocks")
        pages.append(
            {
                "page_num": i + 1,
                "text": text,
                "block_count": len(blocks),
                "has_bbox": len(blocks) > 0,
            }
        )
    result = {
        "page_count": doc.page_count,
        "metadata": doc.metadata,
        "pages": pages,
    }
    doc.close()
    return result


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------


def run_spike() -> None:
    logger.info("=== HWPX LibreOffice 변환 Spike 시작 ===")

    # PyMuPDF 임포트 확인
    try:
        import fitz

        logger.info(f"PyMuPDF 버전: {fitz.__version__}")
    except ImportError:
        logger.error("PyMuPDF 미설치. pip install pymupdf")
        sys.exit(1)

    samples = create_samples()
    results: list[dict[str, Any]] = []

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        for s_info, hwpx_path in zip(SAMPLES, samples):
            logger.info(f"\n--- {hwpx_path.name} ---")
            row: dict[str, Any] = {
                "name": hwpx_path.name,
                "convert": "FAIL",
                "page_count": 0,
                "text_extracted": False,
                "has_bbox": False,
                "sample_text": "",
                "error": "",
            }

            pdf_path = convert_to_pdf(hwpx_path, tmp_path)
            if pdf_path is None:
                row["error"] = "변환 실패"
                results.append(row)
                continue

            row["convert"] = "PASS"
            parsed = parse_pdf(pdf_path)
            row["page_count"] = parsed["page_count"]

            all_text = " ".join(p["text"] for p in parsed["pages"])
            row["text_extracted"] = len(all_text.strip()) > 0
            row["has_bbox"] = any(p["has_bbox"] for p in parsed["pages"])
            row["sample_text"] = all_text[:120].replace("\n", " ")

            # 원본 텍스트가 보존됐는지 확인
            expected_texts = [sec["text"][:10] for sec in s_info["sections"]]
            found = sum(1 for t in expected_texts if t in all_text)
            row["text_preservation"] = f"{found}/{len(expected_texts)}"

            logger.info(
                f"페이지: {row['page_count']} | "
                f"텍스트: {'O' if row['text_extracted'] else 'X'} | "
                f"BBox: {'O' if row['has_bbox'] else 'X'} | "
                f"원문보존: {row['text_preservation']}"
            )
            results.append(row)

    # 결과 저장
    _save_report(results)
    logger.info(f"\n결과 저장: {RESULT_FILE}")
    logger.info("=== Spike 완료 ===")


def _save_report(results: list[dict[str, Any]]) -> None:
    convert_pass = sum(1 for r in results if r["convert"] == "PASS")
    text_pass = sum(1 for r in results if r.get("text_extracted"))
    bbox_pass = sum(1 for r in results if r.get("has_bbox"))

    lines = [
        "# Spike: HWPX LibreOffice 변환 + PyMuPDF 파싱",
        "",
        "## 환경",
        "- 변환 도구: LibreOffice headless (`soffice --headless --convert-to pdf`)",
        "- 파싱 라이브러리: PyMuPDF (`fitz`)",
        f"- 테스트 샘플: {len(results)}개 HWPX 파일 (직접 생성)",
        "",
        "## 결과 요약",
        f"- 변환 성공: {convert_pass}/{len(results)}",
        f"- 텍스트 추출: {text_pass}/{len(results)}",
        f"- 바운딩 박스 추출: {bbox_pass}/{len(results)}",
        "",
        "## 파일별 상세",
        "",
        "| 파일 | 변환 | 페이지 | 텍스트 | BBox | 원문보존 | 비고 |",
        "|---|---|---|---|---|---|---|",
    ]

    for r in results:
        lines.append(
            f"| {r['name']} | {r['convert']} | {r['page_count']} | "
            f"{'O' if r.get('text_extracted') else 'X'} | "
            f"{'O' if r.get('has_bbox') else 'X'} | "
            f"{r.get('text_preservation', '-')} | {r.get('error', '-')} |"
        )

    lines += [
        "",
        "## 추출 텍스트 샘플",
        "",
    ]
    for r in results:
        if r.get("sample_text"):
            lines.append(f"**{r['name']}**: `{r['sample_text']}`")
            lines.append("")

    lines += [
        "## 판정",
        "",
        f"- 변환: {'PASS' if convert_pass == len(results) else 'PARTIAL/FAIL'}",
        f"- 텍스트 추출: {'PASS' if text_pass == len(results) else 'PARTIAL/FAIL'}",
        f"- 바운딩 박스: {'PASS' if bbox_pass == len(results) else 'PARTIAL/FAIL'}",
        "",
        "## 미확인 사항",
        "- 실제 한글과컴퓨터 작성 HWPX 파일로 변환 품질 추가 검증 필요",
        "- 복잡한 표·그림 포함 문서의 변환 충실도 미확인",
        "- 대용량 HWPX(100페이지+) 변환 시간 미측정",
    ]

    RESULT_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULT_FILE.write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    run_spike()
