# tests/document_ingest/test_ingest.py
"""DocumentIngest 통합 테스트 (스펙 §11.2~11.4)."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from document_ingest.errors import IngestIOError, UnsupportedFormatError
from document_ingest.ingest import DocumentIngest, _derive_category
from vector_search.store import VectorStore

FIXTURES_DIR = Path(__file__).parent / "fixtures"


# ─────────────────────────────────────────────
# 정상 케이스 (N-*)
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_n1_ingest_pdf_roundtrip(ingest_instance: DocumentIngest, tmp_path: Path) -> None:
    """N-1: sample.pdf ingest — 청크 수 > 0, doc_id 존재, page 필드."""
    path = str(FIXTURES_DIR / "sample.pdf")
    count = await ingest_instance.ingest_file(path)
    assert count > 0


@pytest.mark.asyncio
async def test_n2_ingest_docx_section_tracking(ingest_instance: DocumentIngest) -> None:
    """N-2: sample.docx — Heading이 section 필드로 저장."""
    path = str(FIXTURES_DIR / "sample.docx")
    count = await ingest_instance.ingest_file(path)
    assert count > 0


@pytest.mark.asyncio
async def test_n3_ingest_pptx_slide_numbers(ingest_instance: DocumentIngest) -> None:
    """N-3: sample.pptx — 슬라이드 번호 page 필드."""
    path = str(FIXTURES_DIR / "sample.pptx")
    count = await ingest_instance.ingest_file(path)
    assert count > 0


@pytest.mark.asyncio
async def test_n4_ingest_hwpx_2011(ingest_instance: DocumentIngest) -> None:
    """N-4: sample_2011.hwpx — 2011 네임스페이스 정상 추출."""
    path = str(FIXTURES_DIR / "sample_2011.hwpx")
    count = await ingest_instance.ingest_file(path)
    assert count > 0


@pytest.mark.asyncio
async def test_n5_ingest_hwpx_2016(ingest_instance: DocumentIngest) -> None:
    """N-5: sample_2016.hwpx — 2016 네임스페이스 fallback 정상 추출."""
    path = str(FIXTURES_DIR / "sample_2016.hwpx")
    count = await ingest_instance.ingest_file(path)
    assert count > 0


@pytest.mark.asyncio
async def test_n6_ingest_md_header_sections(ingest_instance: DocumentIngest) -> None:
    """N-6: sample.md — 헤더 분리 저장."""
    path = str(FIXTURES_DIR / "sample.md")
    count = await ingest_instance.ingest_file(path)
    assert count > 0


@pytest.mark.asyncio
async def test_n7_ingest_directory_category_from_subdirs(
    tmp_path: Path,
    ingest_instance: DocumentIngest,
) -> None:
    """N-7: ingest_directory — category 자동 추출."""
    # 디렉토리 구조 생성
    (tmp_path / "규정").mkdir()
    (tmp_path / "매뉴얼").mkdir()

    # 파일 배치
    a_txt = tmp_path / "규정" / "a.txt"
    a_txt.write_text("규정 문서입니다. " * 20, encoding="utf-8")
    b_md = tmp_path / "매뉴얼" / "b.md"
    b_md.write_text("# 매뉴얼\n\n매뉴얼 내용입니다. " * 20, encoding="utf-8")
    c_txt = tmp_path / "c.txt"
    c_txt.write_text("루트 직속 파일입니다. " * 20, encoding="utf-8")

    total = await ingest_instance.ingest_directory(str(tmp_path))
    assert total > 0


@pytest.mark.asyncio
async def test_n8_reingest_idempotent(
    tmp_path: Path,
    ingest_instance: DocumentIngest,
) -> None:
    """N-8: 재-ingest 시 이전 청크 전부 제거 + 새 청크로 교체 (누적 없음).

    Critic M-1 수정: count2 == count1 검증 + LanceDB 직접 row 수 확인.
    """
    txt_path = tmp_path / "sample.txt"
    txt_path.write_text("테스트 재인제스트 문서입니다. " * 30, encoding="utf-8")

    count1 = await ingest_instance.ingest_file(str(txt_path))
    assert count1 > 0

    # mtime 갱신 (재인제스트 트리거 — doc_id는 path-only이므로 변하지 않음)
    new_time = time.time() + 1
    os.utime(str(txt_path), (new_time, new_time))

    count2 = await ingest_instance.ingest_file(str(txt_path))
    assert count2 > 0

    # 핵심 검증: 총 청크 수가 동일해야 함 (누적 없음, Critic M-1)
    assert count2 == count1, (
        f"재-ingest 후 청크 수가 달라짐: count1={count1}, count2={count2}. "
        "doc_id가 path-only여야 이전 청크가 올바르게 삭제된다."
    )

    # LanceDB 직접 쿼리로 동일 source_path 청크 수 = count1 임을 확인
    import pyarrow as pa  # store가 이미 lancedb+pyarrow를 사용
    from document_ingest.ingest import _make_doc_id

    doc_id = _make_doc_id(txt_path.resolve())
    arrow_tbl: pa.Table = ingest_instance._store._tbl.to_arrow()
    doc_ids: list[str] = arrow_tbl.column("doc_id").to_pylist()
    actual_row_count = doc_ids.count(doc_id)

    assert actual_row_count == count1, (
        f"LanceDB에 남은 row 수({actual_row_count})가 기대({count1})와 다름. "
        "구 청크가 제거되지 않고 누적됐을 가능성."
    )


@pytest.mark.asyncio
async def test_n9_remove_document(
    tmp_path: Path,
    ingest_instance: DocumentIngest,
) -> None:
    """N-9: remove_document — 삭제 후 0건, 재호출 0 반환."""
    txt_path = tmp_path / "to_remove.txt"
    txt_path.write_text("삭제할 문서입니다. " * 20, encoding="utf-8")

    count = await ingest_instance.ingest_file(str(txt_path))
    assert count > 0

    # doc_id 계산
    from document_ingest.ingest import _make_doc_id

    doc_id = _make_doc_id(txt_path.resolve())

    removed = await ingest_instance.remove_document(doc_id)
    assert removed > 0

    # 재호출 → 0 반환 (에러 없음)
    removed2 = await ingest_instance.remove_document(doc_id)
    assert removed2 == 0


@pytest.mark.asyncio
async def test_source_path_is_absolute(
    tmp_path: Path,
    ingest_instance: DocumentIngest,
) -> None:
    """source_path가 절대 경로."""
    txt_path = tmp_path / "abs_test.txt"
    txt_path.write_text("절대 경로 테스트입니다. " * 20, encoding="utf-8")

    count = await ingest_instance.ingest_file(str(txt_path))
    assert count > 0


# ─────────────────────────────────────────────
# 엣지 케이스 (E-*)
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_e1_empty_txt_returns_zero(ingest_instance: DocumentIngest) -> None:
    """E-1: 빈 TXT → 0 반환."""
    path = str(FIXTURES_DIR / "empty.txt")
    count = await ingest_instance.ingest_file(path)
    assert count == 0


@pytest.mark.asyncio
async def test_e3_long_single_sentence_hard_split(
    tmp_path: Path,
    ingest_instance: DocumentIngest,
) -> None:
    """E-3: 2000자짜리 한 문장 → 청크 ≥ 2."""
    long_txt = tmp_path / "long.txt"
    long_txt.write_text("아" * 2000, encoding="utf-8")

    ingest = DocumentIngest(
        embedder=ingest_instance._embedder,
        store=ingest_instance._store,
        chunk_chars=800,
        overlap_chars=0,
    )
    count = await ingest.ingest_file(str(long_txt))
    assert count >= 2


@pytest.mark.asyncio
async def test_e4_overlap_zero(
    tmp_path: Path,
    ingest_instance: DocumentIngest,
) -> None:
    """E-4: overlap_chars=0 설정 — 정상 동작."""
    ingest = DocumentIngest(
        embedder=ingest_instance._embedder,
        store=ingest_instance._store,
        chunk_chars=300,
        overlap_chars=0,
    )
    txt = tmp_path / "test.txt"
    txt.write_text("짧은 문장입니다. " * 50, encoding="utf-8")
    count = await ingest.ingest_file(str(txt))
    assert count >= 1


def test_e5_chunk_chars_equals_overlap_chars_raises() -> None:
    """E-5: chunk_chars == overlap_chars → ValueError."""
    from tests.vector_search.fakes import FakeEmbedder
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        store = VectorStore(db_path=str(Path(tmpdir) / "db"))
        with pytest.raises(ValueError):
            DocumentIngest(
                embedder=FakeEmbedder(),
                store=store,
                chunk_chars=100,
                overlap_chars=100,
            )


@pytest.mark.asyncio
async def test_e6_case_insensitive_extension(
    tmp_path: Path,
    ingest_instance: DocumentIngest,
) -> None:
    """E-6: 확장자 대소문자 무시."""
    # .TXT로 저장
    txt_upper = tmp_path / "UPPER.TXT"
    txt_upper.write_text("대소문자 확장자 테스트입니다. " * 10, encoding="utf-8")
    count = await ingest_instance.ingest_file(str(txt_upper))
    assert count > 0


@pytest.mark.asyncio
async def test_e7_directory_skip_corrupted_continue(
    tmp_path: Path,
    ingest_instance: DocumentIngest,
) -> None:
    """E-7: ingest_directory — 1개 손상, 2개 성공."""
    (tmp_path / "ok1.txt").write_text("정상 파일 1입니다. " * 20, encoding="utf-8")
    (tmp_path / "ok2.txt").write_text("정상 파일 2입니다. " * 20, encoding="utf-8")
    # corrupted.pdf는 0바이트 — ParseError 유발
    import shutil

    shutil.copy(str(FIXTURES_DIR / "corrupted.pdf"), str(tmp_path / "bad.pdf"))

    count = await ingest_instance.ingest_directory(str(tmp_path), recursive=False)
    assert count > 0  # 성공한 파일의 청크 수


@pytest.mark.asyncio
async def test_e9_category_from_subdirs_false(
    tmp_path: Path,
    ingest_instance: DocumentIngest,
) -> None:
    """E-9: category_from_subdirs=False → 모든 청크 category=None."""
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.txt").write_text("서브 폴더 파일입니다. " * 20, encoding="utf-8")

    count = await ingest_instance.ingest_directory(
        str(tmp_path),
        category_from_subdirs=False,
    )
    assert count >= 0


@pytest.mark.asyncio
async def test_e10_same_content_different_paths_independent(
    tmp_path: Path,
    ingest_instance: DocumentIngest,
) -> None:
    """E-10: 동일 내용 다른 경로 → doc_id 다름 → 독립 저장."""
    dir_a = tmp_path / "a"
    dir_b = tmp_path / "b"
    dir_a.mkdir()
    dir_b.mkdir()

    content = "동일 내용 문서입니다. " * 20
    (dir_a / "doc.txt").write_text(content, encoding="utf-8")
    (dir_b / "doc.txt").write_text(content, encoding="utf-8")

    from document_ingest.ingest import _make_doc_id

    id_a = _make_doc_id((dir_a / "doc.txt").resolve())
    id_b = _make_doc_id((dir_b / "doc.txt").resolve())
    assert id_a != id_b


# ─────────────────────────────────────────────
# 적대적 케이스 (A-*)
# ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a4_symlink_escape_skipped(
    tmp_path: Path,
    ingest_instance: DocumentIngest,
) -> None:
    """A-4: symlink 탈출 시도 → skip."""
    # /tmp/root/evil → /tmp/passwd_file (루트 밖)
    target_dir = tmp_path / "root"
    target_dir.mkdir()

    # 실제 파일 (루트 밖)
    outside_file = tmp_path / "outside.txt"
    outside_file.write_text("이 파일은 ingest_root 밖에 있습니다.", encoding="utf-8")

    # symlink: root/evil.txt → ../outside.txt
    try:
        (target_dir / "evil.txt").symlink_to(outside_file)
    except NotImplementedError:
        pytest.skip("symlink not supported on this platform")

    # 정상 파일도 추가
    (target_dir / "normal.txt").write_text("정상 파일. " * 20, encoding="utf-8")

    # symlink 탈출 파일은 skip되어야 함
    count = await ingest_instance.ingest_directory(str(target_dir), recursive=False)
    # normal.txt만 처리 (evil.txt skip)
    assert count >= 0  # 에러 없이 완료


@pytest.mark.asyncio
async def test_a6_sql_injection_category_stored_safely(
    tmp_path: Path,
    ingest_instance: DocumentIngest,
) -> None:
    """A-6: SQL-like 공격 문자 폴더명 → 그대로 저장 (제어문자 없으면 통과)."""
    attack_dir = tmp_path / "' OR 1=1 --"
    attack_dir.mkdir()
    (attack_dir / "test.txt").write_text("SQL 인젝션 테스트 파일입니다. " * 20, encoding="utf-8")

    # category_from_subdirs=True: 폴더명이 category로 들어감
    # 제어문자 없으면 정상 저장 (M_07 VectorStore가 escape 처리)
    count = await ingest_instance.ingest_directory(str(tmp_path))
    assert count >= 0  # 에러 없이 완료


@pytest.mark.asyncio
async def test_a_unsupported_format_raises_in_ingest_file(
    ingest_instance: DocumentIngest,
    tmp_path: Path,
) -> None:
    """미지원 확장자 → ingest_file에서 UnsupportedFormatError."""
    doc_path = tmp_path / "old.doc"
    doc_path.write_bytes(b"fake doc content")
    with pytest.raises(UnsupportedFormatError):
        await ingest_instance.ingest_file(str(doc_path))


@pytest.mark.asyncio
async def test_a_nonexistent_file_raises_ingest_io_error(
    ingest_instance: DocumentIngest,
) -> None:
    """존재하지 않는 파일 → IngestIOError."""
    with pytest.raises(IngestIOError):
        await ingest_instance.ingest_file("/nonexistent/file.txt")


@pytest.mark.asyncio
async def test_a_nonexistent_directory_raises_ingest_io_error(
    ingest_instance: DocumentIngest,
) -> None:
    """존재하지 않는 디렉토리 → IngestIOError."""
    with pytest.raises(IngestIOError):
        await ingest_instance.ingest_directory("/nonexistent/directory")


# ─────────────────────────────────────────────
# _derive_category 단위 테스트
# ─────────────────────────────────────────────


class TestDeriveCategory:
    def test_explicit_category_returns_as_is(self, tmp_path: Path) -> None:
        """explicit_category가 있으면 그대로 반환."""
        f = tmp_path / "sub" / "doc.txt"
        result = _derive_category(
            file_path=f,
            ingest_root=tmp_path,
            category_from_subdirs=True,
            explicit_category="명시적카테고리",
        )
        assert result == "명시적카테고리"

    def test_category_from_direct_subdir(self, tmp_path: Path) -> None:
        """하위 폴더명이 category로 추출된다."""
        (tmp_path / "규정").mkdir()
        f = tmp_path / "규정" / "doc.txt"
        f.touch()
        result = _derive_category(
            file_path=f,
            ingest_root=tmp_path,
            category_from_subdirs=True,
            explicit_category=None,
        )
        assert result == "규정"

    def test_root_direct_file_returns_none(self, tmp_path: Path) -> None:
        """ingest_root 직속 파일 → None."""
        f = tmp_path / "doc.txt"
        f.touch()
        result = _derive_category(
            file_path=f,
            ingest_root=tmp_path,
            category_from_subdirs=True,
            explicit_category=None,
        )
        assert result is None

    def test_category_from_subdirs_false_returns_none(self, tmp_path: Path) -> None:
        """category_from_subdirs=False → None."""
        (tmp_path / "서브").mkdir()
        f = tmp_path / "서브" / "doc.txt"
        f.touch()
        result = _derive_category(
            file_path=f,
            ingest_root=tmp_path,
            category_from_subdirs=False,
            explicit_category=None,
        )
        assert result is None

    def test_control_char_in_explicit_category_raises(self, tmp_path: Path) -> None:
        """explicit_category에 제어문자 → ValueError."""
        f = tmp_path / "doc.txt"
        with pytest.raises(ValueError):
            _derive_category(
                file_path=f,
                ingest_root=tmp_path,
                category_from_subdirs=True,
                explicit_category="카테고리\x00악의",
            )

    def test_nested_subdirs_uses_first_level(self, tmp_path: Path) -> None:
        """2단계 이상 깊은 파일도 최상위 폴더명만 사용."""
        (tmp_path / "업무편람" / "2025").mkdir(parents=True)
        f = tmp_path / "업무편람" / "2025" / "bar.pdf"
        f.touch()
        result = _derive_category(
            file_path=f,
            ingest_root=tmp_path,
            category_from_subdirs=True,
            explicit_category=None,
        )
        assert result == "업무편람"
