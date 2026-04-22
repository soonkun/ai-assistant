# tests/document_ingest/test_parsers.py
"""파서 단위 테스트 — PDF/DOCX/PPTX/HWPX/TXT/MD."""

from __future__ import annotations

import socket
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from document_ingest.errors import IngestIOError, ParseError
from document_ingest.parsers.docx import _parse_docx
from document_ingest.parsers.hwpx import _parse_hwpx
from document_ingest.parsers.md import _parse_md
from document_ingest.parsers.pdf import _parse_pdf
from document_ingest.parsers.pptx import _parse_pptx
from document_ingest.parsers.txt import _parse_txt

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ─────────────────────────────────────────────
# PDF 파서 테스트
# ─────────────────────────────────────────────


class TestPdfParser:
    def test_pdf_returns_segments_with_page_numbers(self) -> None:
        """N-1: sample.pdf 3페이지 파싱 — 세그먼트 반환 + page 필드."""
        path = str(FIXTURES_DIR / "sample.pdf")
        segs = _parse_pdf(path)
        # 최소 1개 이상 세그먼트 (텍스트 레이어가 있는 페이지)
        assert len(segs) >= 1
        for seg in segs:
            assert isinstance(seg.page, int)
            assert seg.page >= 1
            assert seg.text.strip()

    def test_pdf_page_numbers_are_one_based(self) -> None:
        """페이지 번호가 1-based인지 확인."""
        path = str(FIXTURES_DIR / "sample.pdf")
        segs = _parse_pdf(path)
        pages = [s.page for s in segs]
        assert all(p is not None and p >= 1 for p in pages)

    def test_pdf_bbox_is_none_in_v1(self) -> None:
        """V1에서 bbox는 None."""
        path = str(FIXTURES_DIR / "sample.pdf")
        segs = _parse_pdf(path)
        for seg in segs:
            assert seg.bbox is None

    def test_pdf_section_is_none(self) -> None:
        """PDF section 필드는 None."""
        path = str(FIXTURES_DIR / "sample.pdf")
        segs = _parse_pdf(path)
        for seg in segs:
            assert seg.section is None

    def test_pdf_corrupted_file_raises_parse_error(self) -> None:
        """E-2 변형: 손상된 PDF(0바이트) → ParseError."""
        path = str(FIXTURES_DIR / "corrupted.pdf")
        with pytest.raises(ParseError):
            _parse_pdf(path)

    def test_pdf_nonexistent_raises_parse_error(self) -> None:
        """존재하지 않는 파일 → ParseError."""
        with pytest.raises(ParseError):
            _parse_pdf("/nonexistent/path/file.pdf")


# ─────────────────────────────────────────────
# DOCX 파서 테스트
# ─────────────────────────────────────────────


class TestDocxParser:
    def test_docx_returns_segments_with_section(self) -> None:
        """N-2: sample.docx 파싱 — 섹션 추적."""
        path = str(FIXTURES_DIR / "sample.docx")
        segs = _parse_docx(path)
        assert len(segs) > 0

    def test_docx_heading_tracked_as_section(self) -> None:
        """N-2: Heading 스타일 단락이 section 필드로 추적된다."""
        path = str(FIXTURES_DIR / "sample.docx")
        segs = _parse_docx(path)
        # 서론/본론 Heading 이후 단락들은 section이 설정되어야 함
        sections = {s.section for s in segs if s.section is not None}
        assert len(sections) >= 1  # 최소 1개 heading

    def test_docx_page_is_none(self) -> None:
        """DOCX page 필드는 None."""
        path = str(FIXTURES_DIR / "sample.docx")
        segs = _parse_docx(path)
        for seg in segs:
            assert seg.page is None

    def test_docx_table_rows_included(self) -> None:
        """DOCX 표 행이 세그먼트에 포함된다."""
        path = str(FIXTURES_DIR / "sample.docx")
        segs = _parse_docx(path)
        # 표 행은 " | "로 연결되어 있어야 함
        table_segs = [s for s in segs if " | " in s.text]
        assert len(table_segs) > 0

    def test_docx_corrupted_raises_parse_error(self) -> None:
        """손상된 DOCX → ParseError."""
        corrupted_path = str(FIXTURES_DIR / "corrupted.pdf")
        with pytest.raises(ParseError):
            _parse_docx(corrupted_path)

    def test_docx_xxe_no_network_call(self) -> None:
        """A-3: DOCX 파싱 중 외부 네트워크 호출 없음."""
        path = str(FIXTURES_DIR / "sample.docx")
        # socket.connect를 mock해 외부 연결 시도가 없는지 확인
        original_connect = socket.socket.connect

        network_calls: list[str] = []

        def mock_connect(self: socket.socket, address: object) -> None:
            if isinstance(address, tuple):
                host = address[0]
                # localhost/127.0.0.1은 허용
                if host not in ("127.0.0.1", "localhost", "::1"):
                    network_calls.append(str(address))
            original_connect(self, address)

        with patch.object(socket.socket, "connect", mock_connect):
            _parse_docx(path)

        assert len(network_calls) == 0, f"외부 네트워크 호출 감지: {network_calls}"


# ─────────────────────────────────────────────
# PPTX 파서 테스트
# ─────────────────────────────────────────────


class TestPptxParser:
    def test_pptx_returns_5_slides(self) -> None:
        """N-3: sample.pptx 5슬라이드 → 세그먼트 5건."""
        path = str(FIXTURES_DIR / "sample.pptx")
        segs = _parse_pptx(path)
        assert len(segs) == 5

    def test_pptx_page_numbers_1_to_5(self) -> None:
        """N-3: 각 슬라이드 page ∈ {1..5}."""
        path = str(FIXTURES_DIR / "sample.pptx")
        segs = _parse_pptx(path)
        pages = {s.page for s in segs}
        assert pages == {1, 2, 3, 4, 5}

    def test_pptx_section_is_slide_title(self) -> None:
        """N-3: section = 슬라이드 제목."""
        path = str(FIXTURES_DIR / "sample.pptx")
        segs = _parse_pptx(path)
        for seg in segs:
            assert seg.section is not None
            assert "슬라이드" in seg.section

    def test_pptx_corrupted_raises_parse_error(self) -> None:
        """손상된 PPTX → ParseError."""
        with pytest.raises(ParseError):
            _parse_pptx(str(FIXTURES_DIR / "corrupted.pdf"))


# ─────────────────────────────────────────────
# HWPX 파서 테스트
# ─────────────────────────────────────────────


class TestHwpxParser:
    def test_hwpx_2011_namespace_match(self) -> None:
        """N-4: sample_2011.hwpx — 2011 네임스페이스에서 match."""
        path = str(FIXTURES_DIR / "sample_2011.hwpx")
        segs = _parse_hwpx(path)
        assert len(segs) >= 1
        # 텍스트가 추출되어야 함
        all_text = " ".join(s.text for s in segs)
        assert "2011" in all_text or "단락" in all_text

    def test_hwpx_2016_namespace_fallback(self) -> None:
        """N-5: sample_2016.hwpx — 2011 match 0 → 2016 fallback."""
        path = str(FIXTURES_DIR / "sample_2016.hwpx")
        segs = _parse_hwpx(path)
        assert len(segs) >= 1
        all_text = " ".join(s.text for s in segs)
        assert "2016" in all_text or "단락" in all_text

    def test_hwpx_section_is_xml_filename(self) -> None:
        """HWPX section 필드 = 섹션 XML 파일명."""
        path = str(FIXTURES_DIR / "sample_2011.hwpx")
        segs = _parse_hwpx(path)
        for seg in segs:
            assert seg.section is not None
            assert "Contents/section" in seg.section
            assert seg.section.endswith(".xml")

    def test_hwpx_page_is_none(self) -> None:
        """HWPX page 필드는 None."""
        path = str(FIXTURES_DIR / "sample_2011.hwpx")
        segs = _parse_hwpx(path)
        for seg in segs:
            assert seg.page is None

    def test_hwpx_wrong_namespace_raises_parse_error(self) -> None:
        """A-1: 잘못된 네임스페이스 HWPX → ParseError."""
        path = str(FIXTURES_DIR / "wrong_ns.hwpx")
        with pytest.raises(ParseError, match="no paragraphs found"):
            _parse_hwpx(path)

    def test_hwpx_zip_bomb_blocked(self, tmp_path: Path) -> None:
        """A-2: ZIP 폭탄 — ZipInfo.file_size > 1GB → IngestIOError."""
        # 합성: section0.xml ZipInfo.file_size를 1GB+1로 조작
        hwpx_path = tmp_path / "bomb.hwpx"

        ns_uri = "http://www.hancom.co.kr/hwpml/2011/paragraph"
        section_xml = (
            f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<hp:sec xmlns:hp="{ns_uri}">'
            f"<hp:p><hp:run><hp:t>test</hp:t></hp:run></hp:p>"
            f"</hp:sec>"
        )

        with zipfile.ZipFile(str(hwpx_path), "w") as zf:
            zf.writestr("Contents/section0.xml", section_xml.encode("utf-8"))

        # ZipInfo를 패치해 file_size를 1GB+1로 만듦
        from document_ingest.parsers.hwpx import _MAX_DECOMPRESSED_BYTES

        fake_info = MagicMock()
        fake_info.file_size = _MAX_DECOMPRESSED_BYTES + 1

        original_getinfo = zipfile.ZipFile.getinfo

        def patched_getinfo(self: zipfile.ZipFile, name: str) -> MagicMock:
            if name == "Contents/section0.xml":
                return fake_info
            return original_getinfo(self, name)

        with patch.object(zipfile.ZipFile, "getinfo", patched_getinfo):
            with pytest.raises(IngestIOError, match="decompressed size exceeds limit"):
                _parse_hwpx(str(hwpx_path))

    def test_hwpx_corrupted_zip_raises_parse_error(self, tmp_path: Path) -> None:
        """손상된 ZIP(badzip) → ParseError."""
        bad_path = tmp_path / "bad.hwpx"
        bad_path.write_bytes(b"this is not a zip file")
        with pytest.raises(ParseError):
            _parse_hwpx(str(bad_path))

    def test_hwpx_large_single_paragraph(self, tmp_path: Path) -> None:
        """A-5: 10만자 단락 하나 — ParseError 없이 추출 성공."""
        ns_uri = "http://www.hancom.co.kr/hwpml/2011/paragraph"
        large_text = "한" * 100_000
        section_xml = (
            f'<?xml version="1.0" encoding="UTF-8"?>'
            f'<hp:sec xmlns:hp="{ns_uri}">'
            f"<hp:p><hp:run>"
            + "".join(f"<hp:t>{large_text[i * 1000 : (i + 1) * 1000]}</hp:t>" for i in range(100))
            + "</hp:run></hp:p>"
            "</hp:sec>"
        )
        hwpx_path = tmp_path / "large.hwpx"
        with zipfile.ZipFile(str(hwpx_path), "w") as zf:
            zf.writestr("Contents/section0.xml", section_xml.encode("utf-8"))

        segs = _parse_hwpx(str(hwpx_path))
        assert len(segs) == 1
        assert len(segs[0].text) == 100_000


# ─────────────────────────────────────────────
# TXT 파서 테스트
# ─────────────────────────────────────────────


class TestTxtParser:
    def test_txt_basic(self) -> None:
        """기본 UTF-8 TXT 파싱."""
        path = str(FIXTURES_DIR / "sample.txt")
        segs = _parse_txt(path)
        assert len(segs) == 1
        assert segs[0].page is None
        assert segs[0].section is None
        assert segs[0].text.strip()

    def test_txt_empty_file_returns_empty(self) -> None:
        """E-1: 빈 TXT → [] 반환."""
        path = str(FIXTURES_DIR / "empty.txt")
        segs = _parse_txt(path)
        assert segs == []

    def test_txt_bom_removed(self, tmp_path: Path) -> None:
        """E-8: UTF-8 BOM이 제거되어야 한다."""
        bom_path = tmp_path / "bom.txt"
        bom_path.write_bytes(
            b"\xef\xbb\xbf\xed\x95\x9c\xea\xb5\xad\xec\x96\xb4 \xed\x85\x8c\xec\x8a\xa4\xed\x8a\xb8"
        )
        segs = _parse_txt(str(bom_path))
        assert len(segs) == 1
        assert not segs[0].text.startswith("﻿")


# ─────────────────────────────────────────────
# MD 파서 테스트
# ─────────────────────────────────────────────


class TestMdParser:
    def test_md_header_sections(self) -> None:
        """N-6: sample.md — 헤더 기반 섹션 분리."""
        path = str(FIXTURES_DIR / "sample.md")
        segs = _parse_md(path)
        assert len(segs) >= 1

    def test_md_section_contains_header_text(self) -> None:
        """N-6: section 필드가 헤더 텍스트."""
        path = str(FIXTURES_DIR / "sample.md")
        segs = _parse_md(path)
        sections = {s.section for s in segs}
        # 서론, 본론, 결론 헤더가 section으로
        assert any(s and ("서론" in s or "본론" in s or "결론" in s) for s in sections)

    def test_md_page_is_none(self) -> None:
        """MD page 필드는 None."""
        path = str(FIXTURES_DIR / "sample.md")
        segs = _parse_md(path)
        for seg in segs:
            assert seg.page is None

    def test_md_empty_file(self, tmp_path: Path) -> None:
        """빈 MD 파일 → [] 반환."""
        empty_md = tmp_path / "empty.md"
        empty_md.write_text("", encoding="utf-8")
        segs = _parse_md(str(empty_md))
        assert segs == []
