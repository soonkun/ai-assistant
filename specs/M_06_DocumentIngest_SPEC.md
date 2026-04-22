# M_06 DocumentIngest — 스펙

> 분류: **NEW** — upstream `Open-LLM-VTuber/`에는 대응 구현이 없다. PDF/DOCX/PPTX/HWPX/TXT/MD 파서 + 청킹 + BGE-M3 임베딩 + LanceDB upsert까지를 한 모듈로 제공한다.
>
> 작성 근거: `REQUIREMENTS.md` §0(오프라인)/§2.1(지원 포맷·메타데이터)/§2.2(인용)/§9(성능·메모리), `docs/MODULES.md` L174~L220(M_06 초안)/L222~L279(M_07 계약), `specs/M_07_VectorSearch_SPEC.md` §4(공개 API)/§5.1(LanceDB 스키마)/§15.3(DocumentChunk 공유), `docs/RISKS.md` R-03(HWPX 네임스페이스)/R-09(라이선스), `docs/research/hwpx_spike.md`, `docs/research/hwpx_parser.md`.

---

## 1. 목적과 범위

### 1.1 목적

사용자가 `data/Documents/` 하위 폴더에 배치한 문서를 **구조화된 `DocumentChunk` 리스트**로 변환하고, **BGE-M3 임베딩을 산출해 LanceDB에 멱등 upsert**한다. 상위 폴더명이 자동으로 `category`가 된다. 재-ingest 시 기존 청크는 `doc_id` 단위 삭제 후 새 청크로 교체한다. 본 모듈은 **파싱 + 청킹 + 임베딩 오케스트레이션**만 담당한다.

### 1.2 In-Scope

1. `DocumentIngest` 클래스 — `ingest_file(path, category)`, `ingest_directory(path, recursive, category_from_subdirs)`, `remove_document(doc_id)`.
2. 포맷별 파서 6종(PDF/DOCX/PPTX/HWPX/TXT/MD). 각 포맷은 내부 함수 `_parse_pdf`, `_parse_docx`, `_parse_pptx`, `_parse_hwpx`, `_parse_txt`, `_parse_md`로 디스패치.
3. 청커(`_chunk_segments`) — 문장 경계 존중 + 800자 윈도우 + 100자 오버랩.
4. `doc_id` 생성기 — `SHA-256(source_path_abs)[:32]` (path-only, R1 Critic 검수 후 확정).
5. `chunk_id` 생성기 — UUIDv4 문자열(M_07 스키마 PK).
6. 재-ingest 시 `VectorStore.delete_by_doc_id` → `VectorStore.upsert` 2단계 교체 로직.
7. 단위 테스트(정상 ≥5, 엣지 ≥5, 적대적 ≥3). 합성 픽스처는 **M_06 전용으로 새로 작성**(기존 `tests/fixtures/hwpx/` 3종은 HWPX 네임스페이스가 잘못되어 사용 금지).
8. `scripts/bundle_deps.sh`에 신규 wheel 3종(`pypdfium2`, `python-docx`, `python-pptx`, `markdown-it-py`) 추가.

### 1.3 Out-of-Scope (명시적 제외)

1. **임베딩 모델 로드·추론 내부**: M_07 `Embedder` 책임. 본 모듈은 `embedder.embed_passages(texts)` 호출만.
2. **LanceDB 스키마·쿼리 세부**: M_07 `VectorStore` 책임.
3. **검색·인용 포매팅**: M_07 `RagService.retrieve` / `format_citation`.
4. **LLM 프롬프트·답변 생성**: M_05.
5. **OCR**: 스캔 PDF는 V1에서 텍스트 추출 불가 → 빈 결과 + WARNING 로그. PyMuPDF·Tesseract 도입은 V2 CR.
6. **수식·테이블 구조 보존**: 테이블은 셀 텍스트를 공백 연결. LaTeX 수식은 원문 유지.
7. **자동 재인제스트 / 파일 시스템 워처**: 본 모듈은 명시적 호출(`ingest_directory`)만 제공. watchdog 기반 실시간 감시는 V2.
8. **HWP(구 바이너리 포맷)**: REQUIREMENTS.md §2.1은 "HWP/HWPX"지만 회사 환경이 HWPX 전용(`docs/research/hwpx_spike.md` §결정 변경). pyhwp(AGPL)는 R-09로 금지. V1은 HWPX만.
9. **자동 언어 감지**: BGE-M3가 다국어 지원이므로 쿼리·문서 언어 감지 없이 동일 경로.
10. **이미지·미디어 임베딩**: PDF/PPTX 내 이미지는 스킵. V2 멀티모달 확장 시 별도 파이프라인.
11. **중복 문서 탐지(동일 내용·다른 파일명)**: `doc_id`는 source_path + mtime 기반이므로 동일 내용이 다른 경로로 있으면 별도 문서로 처리.
12. **카테고리 필터 검색 UI**: V1 UI 없음(M_12 범위 밖). `category` 필드는 저장만, V2 필터링 대비.

---

## 2. 요구사항 연결

| REQUIREMENTS.md 항목 | M_06 기여 |
|---|---|
| §0 완전 오프라인 / Windows 10/11 | 모든 파서 라이브러리는 순수 Python 휠(네이티브 C 포함). 외부 네트워크 호출 0건. |
| §2.1 지원 포맷 PDF/DOCX/PPTX/HWPX/TXT/MD | 각 포맷 전용 파서 경로(§5). HWP(바이너리) 제외 근거 §1.3. |
| §2.1 페이지 번호·섹션·바운딩 박스 메타데이터 보존 | PDF → page+bbox, PPTX → page(슬라이드 번호), DOCX → section(Heading), HWPX → section(섹션 파일명), MD → section(헤더), TXT → 전부 None. |
| §2.1 "페이지 내 의미 단위" 청크 | 800자 윈도우 + 100자 오버랩, **문장 경계 존중**(§6.2). 단어 중간 자르기 금지. |
| §2.2 인용용 메타데이터 | `doc_name`/`page`/`section`/`source_path`를 M_07 `SearchHit`이 그대로 표출. |
| §8 임베딩 BGE-M3 | M_07 `Embedder.embed_passages`에 배치 크기 32로 위임. |
| §9 메모리 예산 | 100건 배치 임베딩 피크 ≤ 500 MB. 파서 스트리밍으로 파일 전체를 RAM에 올리지 않음. |
| §9 외부 네트워크 호출 금지 | 모든 파서는 로컬 파일 I/O만. `grep` 회귀 테스트로 검증. |
| §10 단일 사용자 | 단일 프로세스·단일 ingest 세션 전제. 동시 실행 락 없음. |

---

## 3. upstream 재사용 분석

### 3.1 분류: **NEW** (REUSE / EXTEND / DROP 모두 없음)

- `grep -r "pdf\|docx\|pptx\|hwpx\|ingest\|chunk\|DocumentChunk" upstream/Open-LLM-VTuber/src/` 결과(M_07 스펙 §3.1과 동일 방식 검증): 도메인 히트 **0건**. upstream은 음성·TTS·Agent 프레임워크로 문서 파서를 포함하지 않는다.
- 결론: 100% 신규 구현. EXTEND/DROP 대상 없음.

### 3.2 부분 REUSE도 없음

M_07이 upstream 함수 수준 재사용 경로가 없는 것과 동일.

---

## 4. 공개 API

모든 공개 심볼은 `src/document_ingest/__init__.py`에서 re-export.

### 4.1 예외 타입

```python
# src/document_ingest/errors.py
class DocumentIngestError(Exception):
    """M_06 공통 기본 예외."""

class UnsupportedFormatError(DocumentIngestError):
    """확장자가 지원 목록(.pdf/.docx/.pptx/.hwpx/.txt/.md) 밖."""

class ParseError(DocumentIngestError):
    """파일이 손상되었거나 해당 포맷 파서가 텍스트 추출 실패."""

class IngestIOError(DocumentIngestError):
    """경로 부재·권한 부족·mtime 조회 실패 등 파일 시스템 레벨 오류."""
```

### 4.2 `DocumentIngest`

```python
# src/document_ingest/ingest.py
from vector_search.types import DocumentChunk      # M_07에서 정의, 공유 (spec §15.3)
from vector_search import Embedder, VectorStore    # 의존성 주입

class DocumentIngest:
    """파일/폴더 단위 인제스트 파이프라인.

    모든 공개 메서드는 **async def**. 내부의 파서·임베더·스토어 호출은 blocking이므로
    `asyncio.to_thread(...)`(또는 `run_in_executor`)로 감싸 이벤트 루프를 점유하지 않는다.

    Args:
        embedder: M_07 Embedder 인스턴스.
        store:    M_07 VectorStore 인스턴스.
        chunk_chars:   청크 윈도우 크기(문자 단위). 기본 800.
        overlap_chars: 청크 간 오버랩 크기. 기본 100. 0 <= overlap_chars < chunk_chars.
        embed_batch_size: embed_passages 배치 크기. 기본 32 (M_07 기본값과 정합).

    Raises:
        ValueError: chunk_chars <= 0 또는 overlap_chars >= chunk_chars.
    """

    def __init__(
        self,
        embedder: Embedder,
        store: VectorStore,
        chunk_chars: int = 800,
        overlap_chars: int = 100,
        embed_batch_size: int = 32,
    ) -> None: ...

    async def ingest_file(
        self,
        path: str,
        category: str | None = None,
    ) -> int:
        """단일 파일을 읽어 청크 생성 → 임베딩 → upsert.

        흐름:
          1. `path` 절대 경로 변환·존재 확인 → 부재 시 `IngestIOError`.
          2. 확장자로 파서 선택 → 미지원 시 `UnsupportedFormatError`.
          3. 파서 호출 → `list[_Segment]` (§6.1 내부 데이터 구조).
          4. 청커 호출 → `list[DocumentChunk]`.
          5. `doc_id`로 기존 청크 삭제(`store.delete_by_doc_id`).
          6. `embedder.embed_passages(texts)` 배치 임베딩.
          7. `store.upsert(chunks, vectors)` 호출.
          8. 반환: upsert된 청크 수(LanceDB 실제 written row 수).

        빈 문서(파싱 결과 텍스트 0자) → 0 반환 + WARNING 로그. 예외 아님.

        Raises:
            UnsupportedFormatError: 확장자 미지원.
            IngestIOError: 파일 부재·권한 부족.
            ParseError: 파서 내부 실패(손상 파일).
            EmbedderError / VectorStoreError: M_07 하위 예외 전파.
        """

    async def ingest_directory(
        self,
        path: str,
        recursive: bool = True,
        category_from_subdirs: bool = True,
    ) -> int:
        """디렉토리 내 지원 확장자 파일을 일괄 인제스트.

        - `recursive=True`(기본): 하위 모든 폴더 재귀 스캔.
        - `category_from_subdirs=True`(기본): `path` 직속 하위 폴더명을 category로 사용.
          예) `ingest_directory("data/Documents/")` 호출 시
              `data/Documents/업무편람/foo.hwpx` → category="업무편람".
              `data/Documents/업무편람/2025/bar.pdf` → category="업무편람" (최상위 1단계만).
          `path` 직속 파일(폴더 없이)은 category=None.
        - `category_from_subdirs=False`: 모든 파일을 category=None으로 등록.

        개별 파일 실패(ParseError/UnsupportedFormatError)는 **로그 경고 + skip**,
        전체 배치를 중단하지 않는다. IO 레벨 치명 오류(IngestIOError, 디렉토리 자체 부재)는 즉시 raise.

        Returns:
            전체 성공 파일들의 upsert된 청크 수 합.
        """

    async def remove_document(self, doc_id: str) -> int:
        """특정 doc_id의 모든 청크를 삭제.

        내부적으로 `store.delete_by_doc_id(doc_id)` 호출. 존재하지 않는 doc_id는 0 반환.

        Returns:
            삭제된 row 수.
        """
```

### 4.3 지원 확장자 테이블

```python
# src/document_ingest/formats.py
SUPPORTED_EXTENSIONS: frozenset[str] = frozenset({
    ".pdf", ".docx", ".pptx", ".hwpx", ".txt", ".md", ".markdown",
})
# 대소문자 무시. 내부적으로 `.casefold()` 비교.
```

`.markdown`은 `.md`와 동일 처리(Markdown 관용). `.doc`/`.ppt`/`.hwp`(바이너리)는 **미지원** → `UnsupportedFormatError`.

---

## 5. 포맷별 파서 전략

각 파서는 `list[_Segment]`를 반환한다(§6.1). 청킹·doc_id 생성은 공통 경로.

### 5.1 PDF — `pypdfium2`

- 라이브러리: `pypdfium2>=4.30,<5` (Apache-2.0, PDFium 기반, 순수 휠).
- 경로:
  ```python
  pdf = pdfium.PdfDocument(path)
  for page_idx, page in enumerate(pdf, start=1):
      textpage = page.get_textpage()
      # 방식 A (권장): get_text_bounded()로 전체 텍스트 + bbox는 단락 단위 추출
      # 방식 B: get_text_range()로 텍스트 범위별 rect 계산
      # V1은 방식 A로 단순화: 페이지 전체 텍스트 1덩어리 + bbox=None.
      raw_text = textpage.get_text_bounded() or ""
      segments.append(_Segment(text=raw_text, page=page_idx, section=None, bbox=None))
  ```
- **bbox는 V1에서 `None`**으로 저장한다. 근거: pypdfium2의 `get_textpage().get_rect()` API로 단락 단위 bbox를 추출하려면 텍스트 블록 검출 로직을 직접 구현해야 함. V1 스코프 초과. **M_07 `SearchHit.bbox`는 Optional**이고 M_12 Frontend는 bbox가 있을 때만 하이라이트를 시도하므로(M_12 스펙) 기능 기본 동작에 문제 없음. V2에서 PyMuPDF로 교체 또는 pypdfium2 단락 클러스터링 도입.
- 스캔 PDF(이미지만, 텍스트 레이어 없음) → `raw_text == ""` → 해당 페이지 skip. 모든 페이지가 빈 문자열이면 빈 문서로 처리(0 청크).
- 성능: 100페이지 PDF p95 ≤ 2s (pypdfium2 네이티브).

### 5.2 DOCX — `python-docx`

- 라이브러리: `python-docx>=1.1,<2` (MIT).
- 경로:
  ```python
  doc = docx.Document(path)
  current_heading: str | None = None
  for para in doc.paragraphs:
      style = para.style.name if para.style else ""
      if style.startswith("Heading"):
          current_heading = para.text.strip() or current_heading
      if para.text.strip():
          segments.append(_Segment(text=para.text, page=None, section=current_heading, bbox=None))
  # 표: para 순회로 잡히지 않으므로 doc.tables를 별도 순회
  for table in doc.tables:
      for row in table.rows:
          row_text = " | ".join(cell.text.strip() for cell in row.cells if cell.text.strip())
          if row_text:
              segments.append(_Segment(text=row_text, page=None, section=current_heading, bbox=None))
  ```
- `page`는 DOCX 특성상 결정 불가(렌더러가 계산) → 항상 `None`.
- `section`은 가장 최근 Heading 스타일 단락의 text.
- 빈 `para.text` / 이미지 단락은 skip.

### 5.3 PPTX — `python-pptx`

- 라이브러리: `python-pptx>=1.0,<2` (MIT).
- 경로:
  ```python
  prs = pptx.Presentation(path)
  for slide_idx, slide in enumerate(prs.slides, start=1):
      slide_title = None
      if slide.shapes.title and slide.shapes.title.has_text_frame:
          slide_title = slide.shapes.title.text_frame.text.strip() or None
      texts: list[str] = []
      for shape in slide.shapes:
          if shape.has_text_frame:
              for para in shape.text_frame.paragraphs:
                  t = "".join(run.text for run in para.runs).strip()
                  if t:
                      texts.append(t)
      combined = "\n".join(texts)
      if combined:
          segments.append(_Segment(text=combined, page=slide_idx, section=slide_title, bbox=None))
  ```
- `page` = 슬라이드 번호(1-based).
- `section` = 해당 슬라이드 제목(없으면 None).
- 노트(speaker notes)는 V1 범위 밖(skip).

### 5.4 HWPX — `zipfile` + `xml.etree.ElementTree`

- 라이브러리: 표준 라이브러리만. `lxml` 불필요(`xml.etree`로 충분, 오프라인 의존성 최소화).
- **네임스페이스 2종 모두 시도**(R-03 완화):
  ```python
  HWPX_NS = {
      "hp":   "http://www.hancom.co.kr/hwpml/2011/paragraph",
      "hp10": "http://www.hancom.co.kr/hwpml/2016/paragraph",
  }
  ```
  기존 `docs/research/hwpx_spike.md`의 `urn:hancom:names:tc:opendocument:xmlns:paragraph:1.0`는 합성 픽스처 기준으로 잘못된 값이다. 실제 한글과컴퓨터가 생성하는 파일은 위 2개 URI를 사용한다(실파일 `data/Documents/업무편람/*.hwpx` 검증 완료).
- 경로:
  ```python
  with zipfile.ZipFile(path) as z:
      section_names = sorted(n for n in z.namelist()
                             if n.startswith("Contents/section") and n.endswith(".xml"))
      for sec_name in section_names:
          xml_bytes = z.read(sec_name)
          root = ET.fromstring(xml_bytes)
          # 두 네임스페이스 모두 시도 — 둘 중 하나에서 <p> 단락이 나오면 성공
          paragraphs = root.findall(".//hp:p", HWPX_NS) or \
                       root.findall(".//hp10:p", HWPX_NS)
          for p in paragraphs:
              # hp:t 또는 hp10:t 텍스트 노드
              runs = p.findall(".//hp:t", HWPX_NS) or p.findall(".//hp10:t", HWPX_NS)
              text = "".join(t.text or "" for t in runs).strip()
              if text:
                  segments.append(_Segment(
                      text=text,
                      page=None,
                      section=sec_name,  # 예: "Contents/section0.xml"
                      bbox=None,
                  ))
  ```
- `page` = None(HWPX는 렌더러가 페이지 계산, `docs/research/hwpx_spike.md` 미확인 사항 §).
- `section` = 섹션 XML 파일명(`Contents/section0.xml` 등). 사용자에게 "섹션 1", "섹션 2"로 보이도록 M_07 `format_citation`이 처리할지는 V1에서 정하지 않고, 파일명 그대로 저장한다(인용 문자열에 그대로 노출되어도 정보 손실 없음).
- 네임스페이스 2종 모두에서 단락 0건이면 → `ParseError("hwpx: no paragraphs found under known namespaces")` + WARNING 로그, 해당 파일만 skip(`ingest_directory` 경로).
- 표·이미지는 V1 범위 밖(`<hp:tbl>` 등 태그 스킵).

### 5.5 TXT — 표준 라이브러리

- 라이브러리: `pathlib` + 표준 `open(encoding="utf-8", errors="replace")`.
- 경로:
  ```python
  text = Path(path).read_text(encoding="utf-8", errors="replace")
  # UTF-8 BOM 제거
  if text.startswith("﻿"):
      text = text[1:]
  if text.strip():
      segments.append(_Segment(text=text, page=None, section=None, bbox=None))
  ```
- 인코딩 실패 시 `errors="replace"`로 무해하게 처리(손실 허용, 로그 경고).
- `cp949` / `euc-kr` 등 한국어 레거시 인코딩은 V1 **UTF-8 전제**. 필요 시 V2 CR로 `chardet` 도입.

### 5.6 MD — `markdown-it-py`

- 라이브러리: `markdown-it-py>=3.0,<4` (MIT).
- 경로:
  ```python
  import markdown_it
  md = markdown_it.MarkdownIt("commonmark")
  text = Path(path).read_text(encoding="utf-8", errors="replace")
  tokens = md.parse(text)
  # 헤더 태그를 따라가며 section 상태 추적
  current_heading: str | None = None
  buffer: list[str] = []
  for tok in tokens:
      if tok.type == "heading_open":
          # flush 이전 섹션
          if buffer:
              segments.append(_Segment(text="\n".join(buffer), page=None,
                                       section=current_heading, bbox=None))
              buffer = []
          # 다음 inline 토큰의 content가 헤더 텍스트
          current_heading = "__pending_heading__"
      elif tok.type == "inline" and current_heading == "__pending_heading__":
          current_heading = tok.content.strip() or None
      elif tok.type == "inline":
          if tok.content.strip():
              buffer.append(tok.content)
  if buffer:
      segments.append(_Segment(text="\n".join(buffer), page=None,
                               section=current_heading, bbox=None))
  ```
- `page` = None(MD는 페이지 개념 없음).
- `section` = 가장 최근 `# / ## / ###` 헤더 텍스트.

---

## 6. 내부 데이터 구조 / 청킹 전략

### 6.1 `_Segment` (내부 전용, public 아님)

```python
# src/document_ingest/segments.py
from dataclasses import dataclass

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
```

### 6.2 청커 동작 (`_chunk_segments`)

입력: `list[_Segment]`, `chunk_chars=800`, `overlap_chars=100`.
출력: `list[DocumentChunk]` (chunk_id는 UUIDv4, doc_id/doc_name/category/source_path는 호출자가 주입).

알고리즘:

1. 각 `_Segment`를 **독립적으로** 청킹한다(세그먼트 경계를 넘지 않음). 근거: PDF page 2의 텍스트가 page 3과 이어진 하나의 청크가 되면 `page` 메타데이터가 손상된다.
2. 세그먼트 내 문장 분할: 한국어·영어 혼합 정규식 `(?<=[.!?。！？])\s+|(?<=다\.)\s+|\n{2,}`로 분할(한국어 종결어미 `다.` 포함).
3. 문장을 순차 누적하며 길이가 `chunk_chars`를 초과하기 직전에 현재 청크를 닫는다.
4. 다음 청크는 **직전 청크의 마지막 `overlap_chars` 문자**로 시작한다. 단 문장 단위로 맞추기 위해 overlap 문자 위치에서 가장 가까운 **이전** 문장 경계를 찾아 시작점 조정.
5. 단일 문장이 `chunk_chars`보다 크면:
   - **분할 허용**(하드 컷). 단어 중간 자르기 방지: 가능한 한 공백 또는 한국어 음절 경계에서 분할.
   - 극단적으로 공백이 없는 경우(예: URL 한 줄 10000자) `chunk_chars` 위치에서 강제 컷.
6. 공백만 남는 청크(스트립 후 < 10자)는 drop.

검증 케이스:

- 800자 이하 짧은 세그먼트 → 1청크.
- 2000자 세그먼트 → ~3청크, 인접 청크 간 100자 오버랩.
- 빈 세그먼트 → 0청크(방어: 파서에서 이미 걸러짐).

### 6.3 `DocumentChunk` 생성

```python
# 호출 측 의사코드
doc_id = hashlib.sha256(
    str(abs_path).encode("utf-8")
).hexdigest()[:32]  # path-only (mtime 제외 — R1 Critic 검수에서 확정)
doc_name = Path(abs_path).name
category_val = _derive_category(abs_path, root, category_from_subdirs, explicit_category)

for seg in segments:
    for chunk_text in chunker.split(seg):
        chunks.append(DocumentChunk(
            doc_id=doc_id,
            doc_name=doc_name,
            category=category_val,
            page=seg.page,
            section=seg.section,
            chunk_id=str(uuid.uuid4()),
            text=chunk_text,
            bbox=seg.bbox,
            source_path=str(abs_path),
        ))
```

### 6.4 `doc_id` 결정

- 수식: `SHA-256( abs_path )` 의 hex digest 앞 **32자** 사용 (path-only).
- 앞 32자 사용 근거: LanceDB `where "doc_id = '...'"` 쿼리 비교 비용 최소화. 32자면 2^128 공간으로 충돌 사실상 불가(단일 사용자 1만 문서 스케일).
- **mtime 미포함 근거** (R1 Critic 검수 후 확정): mtime을 포함하면 파일 수정 시 doc_id가 변경되어 `delete_by_doc_id`가 구 청크를 찾지 못해 중복 누적이 발생한다. 재-ingest 멱등성(§7.1)을 보장하려면 doc_id는 source_path에만 의존해야 한다.
- V1은 content hash를 쓰지 않는다(큰 PDF 해싱 비용). V2에서 content hash 전환 가능.

### 6.5 `category` 결정 (`_derive_category`)

```python
def _derive_category(
    file_path: Path,
    ingest_root: Path | None,     # ingest_directory에서 전달, ingest_file은 None
    category_from_subdirs: bool,
    explicit_category: str | None, # ingest_file(category=...) 인자
) -> str | None:
    if explicit_category is not None:
        return explicit_category
    if ingest_root is None or not category_from_subdirs:
        return None
    # ingest_root 직속 자식 폴더명 추출
    rel = file_path.resolve().relative_to(ingest_root.resolve())
    parts = rel.parts
    if len(parts) <= 1:
        # ingest_root 직속 파일 → None
        return None
    return parts[0]
```

- `category` 최대 길이 100자(M_07 `VectorStore.search` 계약과 정합).
- 공백·제어문자가 포함된 폴더명이면 `strip()` 후 제어문자는 `ValueError`로 거부.

---

## 7. 재-ingest 멱등성

### 7.1 동일 파일 재-ingest 시퀀스

```
ingest_file(path)
  ├─ doc_id = sha256(path, mtime)[:32]
  ├─ store.delete_by_doc_id(doc_id)     # 기존 청크 전부 삭제
  ├─ chunks = parser(path) → chunker()
  ├─ vectors = embedder.embed_passages([c.text for c in chunks])
  └─ store.upsert(chunks, vectors)      # merge_insert(chunk_id)
```

### 7.2 "삭제 → 재-insert" 선택 근거

- M_07 `VectorStore.upsert`는 `chunk_id`(UUIDv4) 기준 멱등. 하지만 재-ingest 시 새 UUIDv4가 생성되므로 기존 chunk_id와 매칭되지 않아 **구 청크가 남는다**.
- 해결: `delete_by_doc_id`로 먼저 전량 삭제 → 새 UUIDv4로 insert.
- 대안(기각): `chunk_id`를 결정론적 hash(`doc_id + seq_no`)로 생성 → 부분 실패 시 구/신 청크 혼재 리스크. V1은 단순한 "모두 지우고 다시 넣기"가 안전.

### 7.3 실패 시 정합성

- `delete_by_doc_id` 성공 후 `upsert` 실패 → 문서가 LanceDB에서 사라진 상태로 남는다.
- V1 허용: 사용자가 `ingest_file`을 재호출하면 회복. 트랜잭션 보장은 LanceDB가 제공하지 않으므로 본 모듈도 시도하지 않음.
- M_07 스펙 §5.3 "부분 실패 리스크"와 동일 판단.

---

## 8. 성능·메모리 예산

### 8.1 성능 목표

| 항목 | 목표 | 근거 |
|---|---|---|
| PDF 100페이지 파싱 | p95 ≤ 2s | pypdfium2 네이티브 SIMD |
| DOCX 1000단락 파싱 | p95 ≤ 1s | python-docx pure Python, O(n) |
| PPTX 50슬라이드 파싱 | p95 ≤ 1s | python-pptx zip+xml |
| HWPX 3000단락(업무편람 규모) 파싱 | p95 ≤ 2s | zip read + ET.fromstring O(n) |
| 청커 10만자 분할 | p95 ≤ 200ms | 정규식 1패스 O(n) |
| `ingest_file` end-to-end(PDF 100p, ~500청크) | p95 ≤ 15s | 파싱 2s + 청킹 < 1s + 임베딩 500청크(16배치) × batch 300ms ≈ 5s + LanceDB upsert < 1s + 여유 |
| `ingest_directory` 10파일 평균 | p95 ≤ 150s | 위 × 10 + 디렉토리 스캔 < 100ms |

### 8.2 메모리 예산

| 컴포넌트 | 피크 RSS | 주석 |
|---|---|---|
| 파서별 중간 텍스트 | ≤ 50 MB | 100MB PDF도 텍스트 레이어는 수 MB |
| 청크 리스트(500 × 800자) | ≤ 5 MB | 문자열 리스트 |
| 배치 임베딩 입력 (batch=32) | ≤ 10 MB | text 리스트 |
| 배치 임베딩 출력 ((32, 1024) float32) | ≤ 150 KB | 배치당 |
| 배치 임베딩 누적((500, 1024) float32) | ≤ 2 MB | |
| **파서+청커+임베딩 피크 합** | ≤ 500 MB | M_07 Embedder 상주 2.2 GB와 별개 |

### 8.3 동시성

- `DocumentIngest`는 **단일 세션 사용** 전제. `ingest_directory`가 파일을 순차 처리한다(병렬화 없음).
- 근거:
  1. 단일 LanceDB writer 제약(M_07 스펙 §8.4).
  2. BGE-M3 embedder 동시 호출은 torch GIL 경합으로 속도 이득 없음.
  3. 디스크 I/O가 bottleneck일 때 동시 파서는 오히려 cache 경합 유발.
- V2에서 파싱 단계만 `ThreadPoolExecutor`로 병렬화 고려(임베딩·저장은 여전히 직렬).

### 8.4 Large 파일 방어

- 파일 크기 상한: `ingest_file`은 파일을 열기 전에 `os.path.getsize(path)` 확인. **100 MB 초과**면 WARNING 로그 + 진행(에러 아님). 1 GB 초과면 `IngestIOError("file too large: {size} bytes > 1GB limit")`.
- 근거: 단일 사용자 오프라인 환경에서 1GB PDF는 실무상 ingest 대상으로 부적합. 메모리 스파이크·OOM 방어.

---

## 9. 에러 처리 정책

| 상황 | 반응 | 예외 raise? | 로그 |
|---|---|---|---|
| `path` 부재 (ingest_file) | `IngestIOError` | yes | ERROR |
| 확장자 미지원 (ingest_file) | `UnsupportedFormatError` | yes | WARNING |
| 확장자 미지원 (ingest_directory 순회 중) | 해당 파일 skip | no | DEBUG |
| 파서 내부 실패(zip 깨짐, XML malformed 등) | `ParseError` | yes | ERROR |
| 파서 내부 실패 (ingest_directory 순회 중) | 해당 파일 skip + 다음 파일 계속 | no | WARNING |
| 파싱 결과 0 세그먼트 (빈 문서) | 0 청크 반환 | no | WARNING |
| HWPX 네임스페이스 2종 모두 match 0 | `ParseError("hwpx: no paragraphs found")` | yes | WARNING |
| 파일 크기 > 100 MB | 경고 + 진행 | no | WARNING |
| 파일 크기 > 1 GB | `IngestIOError` | yes | ERROR |
| `category_from_subdirs=True`지만 `ingest_root` 외부 경로 | `ValueError` | yes | ERROR |
| `category` 값에 제어문자 (폴더명) | `ValueError` | yes | ERROR |
| embedder / store 예외 | 상위로 전파 | yes | ERROR |
| `remove_document` 미존재 doc_id | 0 반환 | no | DEBUG |
| UTF-8 디코딩 실패 (TXT/MD) | `errors="replace"` 로 진행 | no | WARNING |
| mtime 조회 실패 (파일 잠김 등) | `IngestIOError` | yes | ERROR |

### 9.1 원칙

- `ingest_file`은 **fail-fast**: 예외를 삼키지 않고 호출자(테스트·M_01 startup)에게 전달.
- `ingest_directory`는 **best-effort batch**: 개별 파일 실패를 건너뛰며 가능한 파일을 모두 처리. IO 레벨 치명 오류는 즉시 raise.
- 모든 skip 결정은 `logger.warning(..., extra={"path": ..., "reason": ...})`로 기록.

---

## 10. 설정(conf.yaml) 노출

M_01 AppCore가 본 모듈을 생성할 때 사용할 키 목록:

```yaml
ingest:
  documents_root: "data/Documents"   # 사용자가 파일을 배치하는 루트
  chunk_chars: 800
  overlap_chars: 100
  embed_batch_size: 32
  max_file_size_warn_mb: 100         # 이 초과 시 경고
  max_file_size_error_mb: 1024       # 이 초과 시 에러
```

- `ingest.documents_root`는 사용자 정의. 본 스펙은 기본값만 명시.
- 부팅 시 자동 스캔 여부는 M_01 스펙 범위. 본 모듈은 명시적 호출 API만 제공.

---

## 11. 테스트 케이스

경로: `tests/document_ingest/`. `pytest-asyncio` 필요(공개 API async).

### 11.1 공통 픽스처

```text
conftest.py:
  - tmp_store(tmp_path) — 실제 LanceDB VectorStore (M_07 동일 전략)
  - fake_embedder — M_07 tests/vector_search/fakes.FakeEmbedder 재사용 (결정론적 해시)
  - ingest_instance(tmp_store, fake_embedder) — DocumentIngest 인스턴스

fixtures/:
  - sample.pdf       — 3페이지 합성(한국어+영어) pypdfium2로 생성 또는 reportlab으로 생성
  - sample.docx      — Heading 2개 + 단락 10개 + 표 1개
  - sample.pptx      — 5슬라이드, 각 제목 있음
  - sample_2011.hwpx — http://www.hancom.co.kr/hwpml/2011/paragraph 네임스페이스
  - sample_2016.hwpx — http://www.hancom.co.kr/hwpml/2016/paragraph 네임스페이스
  - sample.txt       — UTF-8 한국어 200자
  - sample.md        — # 헤더 2종 + 본문
  - corrupted.pdf    — 0바이트 또는 헤더만 있는 손상 파일
  - empty.txt        — 0바이트
```

**중요**: 기존 `tests/fixtures/hwpx/` 3종(`sample1_meeting.hwpx` 등)은 잘못된 네임스페이스 `urn:hancom:...`를 사용하므로 **M_06 테스트에서 재사용 금지**. 새 픽스처를 `tests/document_ingest/fixtures/`에 생성한다.

### 11.2 정상 케이스 (≥ 5)

**N-1. `ingest_file("sample.pdf")` — 3페이지 라운드트립**
- 검증: 반환 값 > 0, LanceDB에 해당 doc_id의 row 존재, 각 chunk의 `page ∈ {1, 2, 3}`, `source_path`가 절대 경로.

**N-2. `ingest_file("sample.docx")` — 섹션 추적**
- 검증: Heading 2종이 `section` 필드로 각각 저장됨. 표 row들은 가장 최근 heading을 section으로 공유.

**N-3. `ingest_file("sample.pptx")` — 슬라이드 번호**
- 검증: 5슬라이드 → 각 chunk의 `page ∈ {1..5}`. 슬라이드 제목이 `section`.

**N-4. `ingest_file("sample_2011.hwpx")` — HWPX 네임스페이스 2011**
- 검증: 단락 텍스트 정상 추출. 2011 namespace에서 match.

**N-5. `ingest_file("sample_2016.hwpx")` — HWPX 네임스페이스 2016**
- 검증: 2011 namespace match 0건 → 2016 namespace fallback에서 match. 단락 정상 추출.

**N-6. `ingest_file("sample.md")` — 헤더 분리**
- 검증: `# 서론`, `## 본론` 각각이 `section` 필드로 나뉘어 저장.

**N-7. `ingest_directory("data_root/")` — category 자동 추출**
- 구조: `data_root/규정/a.txt`, `data_root/매뉴얼/b.md`, `data_root/c.txt` (루트 직속).
- 검증:
  - a.txt 청크 → `category == "규정"`
  - b.md 청크 → `category == "매뉴얼"`
  - c.txt 청크 → `category is None`

**N-8. 재-ingest 멱등**
- `ingest_file("sample.txt")` → upsert 수 N.
- 파일 mtime 갱신 후 재호출 → 기존 청크 삭제 + 새 청크 upsert, 테이블 내 해당 doc_id row 수 = N (중복 누적 없음).

**N-9. `remove_document(doc_id)`**
- ingest_file 후 remove_document → 0건. 재호출 → 0 반환 (에러 없음).

### 11.3 엣지 케이스 (≥ 5)

**E-1. 빈 TXT 파일 → 0 청크**
- `ingest_file("empty.txt")` → 0 반환. 로그 WARNING. 테이블 변화 없음.

**E-2. 텍스트 레이어 없는 스캔 PDF → 0 청크**
- 모든 페이지 `get_text_bounded() == ""` → 빈 세그먼트 → 0 청크 반환. WARNING.

**E-3. 단일 문장이 chunk_chars 초과**
- 2000자짜리 한 문장만 있는 TXT → 청크 ≥ 3개로 강제 분할, 단어 중간 자르지 않음.

**E-4. `overlap_chars == 0` 설정**
- `DocumentIngest(..., overlap_chars=0)` → 청크 간 겹침 0. 인접 청크 경계 검증.

**E-5. chunk_chars == overlap_chars 경계 (invalid)**
- `DocumentIngest(..., chunk_chars=100, overlap_chars=100)` → `ValueError` (생성자).

**E-6. 지원 확장자 대소문자 혼합 (`.PDF`, `.Hwpx`)**
- `ingest_file("FOO.PDF")` → `.casefold()` 비교로 매칭 성공.

**E-7. `ingest_directory` 일부 파일 손상**
- 3파일 중 1개가 `corrupted.pdf` → 나머지 2개는 성공, 손상 파일은 WARNING 로그 + skip. 반환 값은 성공한 파일의 청크 수 합.

**E-8. BOM 포함 UTF-8 TXT**
- `﻿한국어` → BOM 제거 후 텍스트에 `﻿` 없음.

**E-9. `category_from_subdirs=False` 일괄 None**
- 구조는 N-7과 동일하나 `category_from_subdirs=False` → 모든 청크 `category is None`.

**E-10. 동일 내용 다른 경로의 두 파일**
- `/tmp/a/doc.txt`와 `/tmp/b/doc.txt`가 내용 동일하고 mtime 다름 → `doc_id` 다름 → 둘 다 독립 저장. (V1 정책: 내용 중복 탐지 없음)

### 11.4 적대적 케이스 (≥ 3)

**A-1. 잘못된 네임스페이스의 HWPX**
- `docs/research/hwpx_spike.md`에 기술된 `urn:hancom:...` 네임스페이스로 생성된 파일 (합성) → 2011/2016 어느 곳에도 match 0건 → `ParseError` + `ingest_directory`에서 skip.

**A-2. ZIP 폭탄 (압축 해제 시 팽창)**
- `Contents/section0.xml`이 10MB 압축 → 10GB 팽창하는 악의적 HWPX.
- 검증: `zipfile.ZipFile.read()`가 10GB 문자열을 반환하기 전에 `max_file_size_error_mb`(1GB) 체크를 **압축 해제 후 크기**에도 적용. 초과 시 `IngestIOError("decompressed size exceeds limit")`.
- 구현: `ZipInfo.file_size`를 확인해 해제 전 차단.

**A-3. DOCX에 악의적 external reference (XXE)**
- `python-docx`는 내부적으로 `lxml`로 OOXML을 파싱. XXE 공격 가능성 존재.
- 검증: `python-docx`가 기본으로 external entity 처리를 비활성화하는지 확인 테스트(또는 `defusedxml` 도입). 외부 DTD 참조가 있는 DOCX를 로드해도 네트워크 호출 0건 확인(`socket.socket.connect`를 mock해 assert_not_called).
- 방어 구현: `python-docx` 호출 전에 `defusedxml.defuse_stdlib()` 호출(한 번만). `pyproject.toml`에 `defusedxml>=0.7,<1` 추가.

**A-4. 경로 탈출 (symlink 공격)**
- `ingest_directory("/tmp/root")` 내부에 `/tmp/root/evil -> /etc/passwd` 심볼릭 링크.
- 검증: `Path.resolve()` 후 `ingest_root`에 속하지 않으면 skip + WARNING. `/etc/passwd`를 읽지 않는다.

**A-5. 매우 큰 HWPX 단락 (10만 문자 한 단락)**
- `<hp:p>` 하나가 `<hp:t>` 1000개를 포함해 합쳐 10만자.
- 검증: 청커가 hard-split로 처리, 메모리 스파이크 ≤ 500MB 유지(§8.2).

**A-6. category 이름에 SQL-like 공격 문자**
- 폴더명이 `"' OR 1=1 --"` → `_derive_category`가 제어문자 없음 확인 후 그대로 반환 → M_07 `VectorStore.upsert`가 저장 시 그대로 문자열로 저장(search 시 escape는 M_07 책임). 본 모듈은 **category 값 그대로 전달**하되, 제어문자(0x00~0x1F) 포함 시만 거부.
- 검증: 공격 문자열 폴더도 정상 저장되며, 이후 M_07 `search(category="...")`가 escape해 안전 동작.

---

## 12. Definition of Done

### 12.1 공통 (CLAUDE.md "산출물 체크리스트")

- [ ] `specs/M_06_DocumentIngest_SPEC.md` (본 파일, 사용자 승인).
- [ ] `src/document_ingest/` 구현 (§14 구조).
- [ ] `tests/document_ingest/` 정상 ≥ 5, 엣지 ≥ 5, 적대적 ≥ 3.
- [ ] `ruff format .`, `ruff check .`, `mypy src/document_ingest`, `pytest tests/document_ingest -v` 모두 통과.
- [ ] `reviews/M_06_DocumentIngest_REVIEW.md` Critic PASS.
- [ ] `docs/MODULES.md` M_06 상태 `🔲 HOLD` → `✅ DONE`.

### 12.2 M_06 고유 DoD

- [ ] 6개 포맷 모두 최소 1개 정상 케이스 테스트 통과(PDF/DOCX/PPTX/HWPX/TXT/MD).
- [ ] HWPX 2011·2016 네임스페이스 양방 match 확인(N-4, N-5).
- [ ] 실제 사내 파일 `data/Documents/업무편람/식량원 기술지원과 업무편람(2025).hwpx` 로컬 smoke 테스트에서 ≥ 1000 단락 추출(Windows/macOS dev 환경, `@pytest.mark.slow`).
- [ ] `ingest_directory`가 category 자동 추출 + 개별 파일 실패 skip 동작(N-7, E-7).
- [ ] 재-ingest 시 이전 청크 전부 제거되고 새 청크로 교체(N-8).
- [ ] 청크 경계가 단어 중간을 자르지 않음을 단위 테스트로 증명.
- [ ] 단일 `ingest_file(sample.pdf, 3페이지)` CPU 평균 end-to-end ≤ 10s(p95 ≤ 15s).

### 12.3 M_07 경계 계약

- [ ] `DocumentChunk`를 `src/document_ingest/` 내부에 **복제 정의하지 않고** `from vector_search.types import DocumentChunk`로 import (M_07 스펙 §15.3).
- [ ] `VectorStore.delete_by_doc_id` → `VectorStore.upsert` 순서 호출. 호출 사이에 다른 write 없음.
- [ ] `Embedder.embed_passages(texts)` 배치 크기 32로 호출. 1회 호출당 텍스트 수 ≤ 32.
- [ ] 생성된 `DocumentChunk.text`는 비지 않음(len ≥ 10 after strip).
- [ ] 생성된 `DocumentChunk.chunk_id`는 UUIDv4 형식(`uuid.UUID(hit.chunk_id)` 파싱 성공).

### 12.4 의존성·빌드

- [ ] `pyproject.toml`에 추가: `pypdfium2>=4.30,<5`, `python-docx>=1.1,<2`, `python-pptx>=1.0,<2`, `markdown-it-py>=3.0,<4`, `defusedxml>=0.7,<1`. 추가 사유를 커밋 메시지에 기록.
- [ ] `scripts/bundle_deps.sh`에 위 5종 wheel 다운로드 블록 추가.
- [ ] 런타임 네트워크 호출 0건. `grep -r "http\|https\|requests\|urllib\|socket\." src/document_ingest/` 결과에서 네트워크 호출 없음 확인(import 수준 포함).

### 12.5 문서 동기화

- [ ] `docs/MODULES.md` M_06 블록의 HOLD 조건(`assets/hwpx_samples/ 5건 확보`)을 **삭제 또는 재해석**(`data/Documents/` 단일 경로로 일원화). 해당 변경은 M_06 builder PR에서 함께 반영.
- [ ] `docs/RISKS.md` R-03(HWPX 네임스페이스)을 **MITIGATING** 상태로 전환 + 완화 방안 실행 결과(2개 네임스페이스 구현 + 실파일 검증) 기록.
- [ ] `docs/research/hwpx_spike.md`의 잘못된 네임스페이스 부분에 "실제 한글과컴퓨터 파일은 `http://www.hancom.co.kr/hwpml/2011(|2016)/paragraph` 를 사용하므로 M_06은 두 네임스페이스를 모두 시도한다"는 정정 각주를 추가.

### 12.6 무결성

- [ ] `upstream/Open-LLM-VTuber/**` git diff 빈 상태.
- [ ] 본 모듈이 `sentence-transformers`·`lancedb`를 직접 import하지 않음(M_07을 통해서만 접근).
- [ ] `assets/hwpx_samples/` 하위에 파일 생성 안 함. 단일 문서 루트는 `data/Documents/`.

---

## 13. 의존성

### 13.1 신규 Python 패키지

| 패키지 | 버전 핀 | 라이선스 | 용도 | 오프라인 번들 |
|---|---|---|---|---|
| `pypdfium2` | `>=4.30,<5` | Apache-2.0 / BSD-3 | PDF 파싱 | 핵심 |
| `python-docx` | `>=1.1,<2` | MIT | DOCX 파싱 | 핵심 |
| `python-pptx` | `>=1.0,<2` | MIT | PPTX 파싱 | 핵심 |
| `markdown-it-py` | `>=3.0,<4` | MIT | MD 파싱 | 핵심 |
| `defusedxml` | `>=0.7,<1` | Python-2.0 | XXE 방어 | 핵심 |

라이선스는 모두 허용형(상업적 사용·수정·배포 가능). R-09 AGPL 금지 규칙과 정합.

### 13.2 기존 / 표준 라이브러리

- `zipfile`, `xml.etree.ElementTree`, `hashlib`, `uuid`, `pathlib`, `os`, `re`, `logging`, `asyncio` — 표준 라이브러리.
- M_07 `vector_search` 패키지 — `Embedder`, `VectorStore`, `DocumentChunk`, 예외 타입.

### 13.3 모델 파일

- 없음. 임베딩 모델은 M_07 `Embedder`가 관리.

### 13.4 개발 의존성

- `pytest`, `pytest-asyncio`, `pytest-cov` 기존. 신규 없음.

---

## 14. 디렉토리 구조

```
src/document_ingest/
├── __init__.py          # 공개 심볼 re-export
│                        #   from .ingest import DocumentIngest
│                        #   from .errors import (DocumentIngestError, UnsupportedFormatError,
│                        #                        ParseError, IngestIOError)
│                        #   from .formats import SUPPORTED_EXTENSIONS
├── errors.py            # 예외 4종
├── formats.py           # SUPPORTED_EXTENSIONS, 확장자 → 파서 dispatch
├── segments.py          # _Segment dataclass, _chunk_segments 청커
├── ingest.py            # DocumentIngest 본체 + _derive_category + doc_id 생성
└── parsers/
    ├── __init__.py
    ├── pdf.py           # _parse_pdf (pypdfium2)
    ├── docx.py          # _parse_docx (python-docx)
    ├── pptx.py          # _parse_pptx (python-pptx)
    ├── hwpx.py          # _parse_hwpx (zipfile + ET, 2 네임스페이스)
    ├── txt.py           # _parse_txt (stdlib)
    └── md.py            # _parse_md (markdown-it-py)

tests/document_ingest/
# tests/*/__init__.py 생성 금지 (CR-06 정책)
├── conftest.py          # tmp_store, fake_embedder, ingest_instance
├── fixtures/            # 합성 파일 (sample_*.pdf/docx/pptx/hwpx/txt/md, corrupted.pdf, empty.txt)
├── test_formats.py      # 확장자 감지, 대소문자, 미지원 포맷
├── test_parsers_pdf.py  # N-1, E-2
├── test_parsers_docx.py # N-2, A-3 (XXE)
├── test_parsers_pptx.py # N-3
├── test_parsers_hwpx.py # N-4, N-5, A-1, A-2
├── test_parsers_txt.py  # E-1, E-8 (BOM)
├── test_parsers_md.py   # N-6
├── test_chunker.py      # E-3, E-4, E-5, 단어 중간 자르기 없음
├── test_ingest.py       # N-7, N-8, N-9, E-7, E-9, E-10, A-4, A-6
└── test_real_hwpx.py    # @pytest.mark.slow — data/Documents/ 실파일 smoke
```

패키지명 `document_ingest` 채택: 표준 모듈과 충돌 없음. `python-docx`(import `docx`)와 이름 겹침 없음.

---

## 15. 경계 충돌·결정 근거 기록

### 15.1 경계 충돌 A: `DocumentChunk` 정의 위치

**충돌 현상**
- `docs/MODULES.md` L198~L209 초안: M_06이 `DocumentChunk`를 정의한다고 암시.
- `specs/M_07_VectorSearch_SPEC.md` §4.1.1: M_07 `src/vector_search/types.py`에 1곳 정의한다고 확정.

**결정: M_07 정의를 M_06이 import하여 공유**.

**근거**:
1. M_07이 먼저 구현되어 ✅ DONE 상태. `DocumentChunk`는 이미 `vector_search.types`에 존재.
2. 복제 정의는 필드 drift 리스크.
3. M_07 스펙 §15.3의 결정을 존중.

### 15.2 경계 충돌 B: `ingest_file` 반환값 의미

**초안 (MODULES.md)**: "upsert된 청크 수".

**확정**: "LanceDB가 실제로 쓴 row 수"(M_07 `VectorStore.upsert`의 반환값 그대로). 단 M_07 V1에서는 `merge_insert` 통계 미반영으로 `len(chunks)`를 반환한다(M_07 스펙 §17). 본 모듈은 그 값을 그대로 전달.

### 15.3 `_Segment` vs `DocumentChunk` 분리

**왜 중간 타입이 필요한가?**
- 파서는 "의미 단위 블록"(페이지·슬라이드·섹션) 단위로 텍스트를 뽑지만, 이 블록이 청크보다 크거나 작을 수 있다.
- 청커는 `_Segment`를 잘라 `DocumentChunk`를 생성. 이 과정에서 `doc_id`, `chunk_id`, `doc_name`, `category`, `source_path`를 주입해야 하는데, 파서는 이 정보를 알지 못한다(파일 단위 메타데이터).
- `_Segment`는 파서의 책임 범위(text + page/section/bbox)만 담고, 파일 레벨 메타는 호출자가 주입. 책임 분리.

### 15.4 HWPX 네임스페이스 2종 시도

**충돌 현상**
- `docs/research/hwpx_spike.md`의 네임스페이스 `urn:hancom:names:tc:opendocument:xmlns:paragraph:1.0`는 합성 픽스처 기준이며, 실제 한글과컴퓨터가 생성하는 파일은 `http://www.hancom.co.kr/hwpml/2011/paragraph` 또는 `http://www.hancom.co.kr/hwpml/2016/paragraph`를 사용한다.
- `docs/RISKS.md` R-03이 이 리스크를 기록.

**결정**: 본 모듈은 두 네임스페이스(`hp` = 2011, `hp10` = 2016)를 모두 시도한다. R-03 완화.

**기각 안**:
- (a) 루트 엘리먼트 `xmlns` 동적 추출 — R-03 완화안 2에서 제안됐으나, `xml.etree`의 네임스페이스 처리는 prefix 기반 질의가 경직되어 동적 URI 주입이 복잡. 2종 하드코딩이 더 단순하고 실 케이스 99%를 커버.
- (b) `lxml` 도입 + XPath `//*[local-name()='p']` — 네임스페이스 무시 XPath. 외부 의존성 추가 vs 하드코딩 2종의 단순성 trade-off에서 후자 채택.

### 15.5 `bbox`를 PDF도 V1에서 None으로 저장

**충돌 현상**
- `REQUIREMENTS.md` §2.1: "페이지 번호·섹션·바운딩 박스를 메타데이터로 보존".
- `docs/MODULES.md` M_06 L207: "bbox: tuple ... PDF만 채움".
- pypdfium2로 단락 단위 bbox 추출은 블록 클러스터링이 필요 → V1 공수 초과.

**결정**: V1에서는 `bbox=None`으로 저장한다. M_07 `SearchHit.bbox`는 Optional이고 M_12 Frontend는 bbox가 있을 때만 하이라이트하므로 기본 인용 기능(문서명 + 페이지 + 섹션)은 정상 동작.

**후속 조치**: `docs/RISKS.md`에 R-13(새 항목) "PDF bbox 미추출로 인용 하이라이트 정밀도 저하"를 추가하는 CR을 M_06 builder 단계에서 발행. V2에서 PyMuPDF(AGPL 검토 필요) 또는 pypdfium2 블록 클러스터링으로 업그레이드.

### 15.6 동시성 배제

**결정**: `ingest_directory`는 파일을 순차 처리. 병렬화 없음.

**근거** (§8.3 참고):
1. LanceDB 단일 writer 제약.
2. BGE-M3 embedder 동시 호출 이득 없음 (GIL).
3. 디스크 I/O 경합.
4. 단일 사용자 전제(REQUIREMENTS §10)에서 `ingest_directory`는 드문 작업(초기 세팅 또는 분기별 1회). 지연 허용.

### 15.7 `data/Documents/` 단일 루트

**충돌 현상**
- `docs/MODULES.md` M_06 초안: `assets/hwpx_samples/` 5건 확보 후 착수.
- 사용자 방침(2026-04-23): `data/Documents/`를 유일한 RAG 문서 루트로 하고 `assets/hwpx_samples/`는 폐기.

**결정**: 본 모듈은 `data/Documents/`만 인식한다. `assets/hwpx_samples/` 경로를 참조하는 코드 0. 테스트 픽스처는 `tests/document_ingest/fixtures/`에 합성으로 작성.

---

## 16. 스펙 외 사항 (명시적 제외, 재확인)

본 모듈의 책임이 **아닌** 항목:

1. **임베딩 모델 로드·추론 내부 구현** — M_07 `Embedder`.
2. **LanceDB 스키마·쿼리·인덱스** — M_07 `VectorStore`.
3. **검색·인용 포매팅** — M_07 `RagService`.
4. **LLM 프롬프트·답변 생성** — M_05.
5. **PDF 뷰어·bbox 하이라이트 UI** — M_12 Frontend.
6. **OCR·수식·테이블 구조 보존** — V2 범위.
7. **HWP(구 바이너리)·DOC·PPT·오래된 Office 포맷** — V1 제외(R-09 라이선스).
8. **파일 시스템 실시간 감시(watchdog)** — V2.
9. **다국어 감지 / 인코딩 자동 탐지** — UTF-8 전제.
10. **이미지·미디어 임베딩** — V2 멀티모달.
11. **카테고리 필터 검색 UI** — M_12 범위 밖, V1 UI 없음.
12. **사내 위키·Confluence MCP** — REQUIREMENTS §7, 별도 모듈.

---

## 17. 알려진 한계 (V2 이관)

V1 구현에서 의도적으로 단순화한 항목. 현재 스케일(1만 청크, 단일 사용자)에서는 허용 범위.

- **PDF bbox 미추출** (§15.5): V1 `bbox=None`. V2에서 블록 클러스터링 또는 PyMuPDF 도입.
- **HWPX 네임스페이스 하드코딩** (§15.4): 2011·2016 고정. 향후 Hancom이 새 버전을 내놓으면 하드코딩 추가 필요.
- **인코딩 UTF-8 전제**: cp949/euc-kr 레거시 한국어 TXT는 mojibake. `chardet` 도입은 V2 CR.
- **동시 ingest 없음** (§15.6): 대량 일괄 등록 시 시간 소요. V2에서 파싱 병렬화.
- **content hash doc_id 미사용** (§6.4): mtime 변경만으로 재인제스트 발생(불필요 재임베딩 가능). V2에서 content hash로 교체.
- **스캔 PDF OCR 없음** (§1.3): V2에서 Tesseract + 한국어 언어팩 번들링 검토.
- **테이블 구조 미보존** (§1.3): V1은 셀 텍스트 공백 연결. V2에서 Markdown 테이블 복원 또는 구조화 필드 추가.

---
