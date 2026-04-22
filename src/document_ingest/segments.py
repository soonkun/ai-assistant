# src/document_ingest/segments.py
"""_Segment 내부 데이터 구조 + _chunk_segments 청킹 로직 (M_06 스펙 §6)."""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass

from vector_search.types import DocumentChunk

logger = logging.getLogger(__name__)

# 문장 경계 분할 정규식:
# - 영어/범용: .!? 뒤 공백
# - 한국어 종결어미: 다. 요. 임. 죠. 네. 음. 됩니다. 습니다. 등 + 뒤 공백
# - 빈 줄(2개 이상 개행)
_SENTENCE_SPLIT_RE = re.compile(
    r"(?<=[.!?。！？])\s+"
    r"|(?<=다\.)\s+"
    r"|(?<=요\.)\s+"
    r"|(?<=임\.)\s+"
    r"|(?<=죠\.)\s+"
    r"|(?<=네\.)\s+"
    r"|\n{2,}"
)


@dataclass(frozen=True)
class _Segment:
    """파서가 반환하는 중간 단위. 청커의 입력이 된다.

    - 파서별로 다른 경계 개념을 통일: PDF=page, PPTX=slide, DOCX/MD=heading block,
      HWPX=section file, TXT=전체 1건.
    - text는 개행 포함 가능. 빈 문자열은 파서가 이미 걸러서 여기 도달하지 않는다.
    - page/section/bbox는 그대로 DocumentChunk에 전파.
    """

    text: str
    page: int | None
    section: str | None
    bbox: tuple[float, float, float, float] | None


def _split_sentences(text: str) -> list[str]:
    """텍스트를 문장 단위로 분할한다."""
    # 정규식으로 분할하되 빈 항목 제거
    parts = _SENTENCE_SPLIT_RE.split(text)
    sentences = [p.strip() for p in parts if p.strip()]
    return sentences


def _hard_split(text: str, chunk_chars: int) -> list[str]:
    """단일 문장이 chunk_chars보다 클 때 공백/음절 경계에서 강제 분할."""
    chunks: list[str] = []
    while len(text) > chunk_chars:
        # 공백에서 자르는 시도 (chunk_chars 이하의 마지막 공백)
        cut_pos = text.rfind(" ", 0, chunk_chars)
        if cut_pos <= 0:
            # 공백 없으면 chunk_chars 위치에서 강제 컷
            cut_pos = chunk_chars
        part = text[:cut_pos].strip()
        if part:
            chunks.append(part)
        text = text[cut_pos:].strip()
    if text:
        chunks.append(text)
    return chunks


def _chunk_segment(
    seg: _Segment,
    chunk_chars: int,
    overlap_chars: int,
    doc_id: str,
    doc_name: str,
    category: str | None,
    source_path: str,
) -> list[DocumentChunk]:
    """단일 _Segment를 DocumentChunk 리스트로 분할한다.

    스펙 §6.2 알고리즘 구현:
    1. 세그먼트 독립 청킹 (경계 넘지 않음)
    2. 문장 단위 누적
    3. chunk_chars 초과 전 청크 닫기
    4. overlap_chars 오버랩
    5. 단일 문장 > chunk_chars → 하드 컷
    6. 스트립 후 < 10자 drop
    """
    sentences = _split_sentences(seg.text)
    if not sentences:
        return []

    result: list[DocumentChunk] = []

    # 현재 누적 버퍼
    current_sentences: list[str] = []
    current_len: int = 0

    def flush_chunk(sentences_buf: list[str]) -> DocumentChunk | None:
        text = " ".join(sentences_buf).strip()
        if len(text) < 10:
            return None
        return DocumentChunk(
            doc_id=doc_id,
            doc_name=doc_name,
            category=category,
            page=seg.page,
            section=seg.section,
            chunk_id=str(uuid.uuid4()),
            text=text,
            bbox=seg.bbox,
            source_path=source_path,
        )

    for sentence in sentences:
        # 단일 문장이 chunk_chars 초과 → 하드 컷 후 개별 처리
        if len(sentence) > chunk_chars:
            # 먼저 현재 버퍼 flush
            if current_sentences:
                chunk = flush_chunk(current_sentences)
                if chunk:
                    result.append(chunk)
                current_sentences = []
                current_len = 0

            # 하드 컷 결과를 개별 청크로
            hard_parts = _hard_split(sentence, chunk_chars)
            for part in hard_parts:
                chunk = flush_chunk([part])
                if chunk:
                    result.append(chunk)
            continue

        # 추가했을 때 chunk_chars 초과 → 현재 버퍼 flush 후 새 버퍼 시작
        sep_len = 1 if current_sentences else 0  # 공백 구분자
        if current_len + sep_len + len(sentence) > chunk_chars and current_sentences:
            chunk = flush_chunk(current_sentences)
            if chunk:
                result.append(chunk)

            # 오버랩: 이전 청크의 마지막 overlap_chars 문자에 속하는 문장들을 찾아 시작점 조정
            if overlap_chars > 0:
                overlap_sentences: list[str] = []
                overlap_len = 0
                for prev_sentence in reversed(current_sentences):
                    candidate_len = len(prev_sentence) + (1 if overlap_sentences else 0)
                    if overlap_len + candidate_len <= overlap_chars:
                        overlap_sentences.insert(0, prev_sentence)
                        overlap_len += candidate_len
                    else:
                        break
                current_sentences = overlap_sentences
                current_len = overlap_len
            else:
                current_sentences = []
                current_len = 0

        sep_len = 1 if current_sentences else 0
        current_sentences.append(sentence)
        current_len += sep_len + len(sentence)

    # 남은 버퍼 flush
    if current_sentences:
        chunk = flush_chunk(current_sentences)
        if chunk:
            result.append(chunk)

    return result


def chunk_segments(
    segments: list[_Segment],
    chunk_chars: int,
    overlap_chars: int,
    doc_id: str,
    doc_name: str,
    category: str | None,
    source_path: str,
) -> list[DocumentChunk]:
    """여러 _Segment를 독립적으로 청킹해 DocumentChunk 리스트를 반환한다.

    각 세그먼트는 독립 처리(경계를 넘지 않음, 스펙 §6.2.1).
    """
    result: list[DocumentChunk] = []
    for seg in segments:
        chunks = _chunk_segment(
            seg=seg,
            chunk_chars=chunk_chars,
            overlap_chars=overlap_chars,
            doc_id=doc_id,
            doc_name=doc_name,
            category=category,
            source_path=source_path,
        )
        result.extend(chunks)
    return result
