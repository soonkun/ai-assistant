# M_07 VectorSearch — 스펙

> 분류: **NEW** — upstream `Open-LLM-VTuber/`에는 대응 구현이 없다. BGE-M3 임베딩 + LanceDB 저장/검색 + 한국어 인용 포매터를 한 모듈에 집중한다.
>
> 작성 근거: `REQUIREMENTS.md` §0(오프라인)/§2.1~§2.2(RAG 인용)/§8(임베딩 모델)/§9(메모리·응답 지연), `docs/ARCHITECTURE.md` §1/§3.2/§5 D-01/D-05/§6.1, `docs/MODULES.md` M_07(L222~L266)/M_06(L174~L220), `docs/RISKS.md` R-02/R-07, `docs/MILESTONES.md` M_07(L77~L86), `docs/research/bge_m3_korean.md`, `src/tool_router/router.py` L229~L272, `src/tool_router/schemas.py` L80~L115.

---

## 1. 목적과 범위

### 1.1 목적

사내 등록 문서의 **임베딩 생성 / 벡터 저장·검색 / 인용 문자열 포매팅**을 한 모듈로 제공한다. Gemma 4 E4B가 `search_docs` 툴을 호출하면 `ToolRouter._handle_search_docs`가 본 모듈의 `RagService.retrieve()`를 executor에 밀어 넣고, 본 모듈은 결정론적으로 `RetrievalResult`를 반환한다. "관련 문서 없음" 판정도 본 모듈이 책임진다.

### 1.2 In-Scope

1. `Embedder` — BGE-M3 로컬 모델을 `sentence-transformers`로 로드, `embed_passages(list[str]) -> np.ndarray`, `embed_query(str) -> np.ndarray`.
2. `VectorStore` — LanceDB 테이블 `chunks` 생성·열기, `upsert(chunks, vectors)`, `search(query_vec, top_k, category)`, `delete_by_doc_id(doc_id)`.
3. `RagService` — `Embedder` + `VectorStore` 조합, `retrieve(query, top_k, category)`, `format_citation(hit)`.
4. 공개 데이터 타입 — `DocumentChunk`(§4.1, M_06과 공유), `SearchHit`(§4.2, **평면 dataclass**), `RetrievalResult`(§4.3).
5. 예외 타입 — `VectorSearchError`, `EmbedderError`, `VectorStoreError`, `RetrievalError`.
6. 단위 테스트(정상 ≥5, 엣지 ≥5, 적대적 ≥3) — `Embedder`는 FakeEmbedder fixture로 대체, LanceDB는 `tmp_path` 실 인스턴스 사용.
7. `conf.yaml` 노출 훅 — `rag.min_score`, `rag.top_k_default`, `rag.db_path`, `rag.embedder_model_dir`.
8. `ToolRouter` 호출 계약과의 **평면 필드 정합성 보장**(§4.2, §15).

### 1.3 Out-of-Scope (명시적 제외)

1. **문서 파싱·청킹**: M_06 DocumentIngest 책임. 본 모듈은 `DocumentChunk`를 **입력으로만** 수용한다.
2. **리랭커(Qwen3-Reranker-8B 등)**: `docs/ARCHITECTURE.md` D-05로 V1 제외. 리랭커 API surface는 노출하지 않는다.
3. **하이브리드 검색**(BM25+Dense 퓨전): REQUIREMENTS.md에 없음. V1 dense-only.
4. **자동 카테고리 분류**: M_06이 폴더명으로 결정한 `category`를 그대로 저장·필터.
5. **답변 생성·LLM 호출**: Gemma는 M_05 책임. 본 모듈은 검색 결과만 반환.
6. **PDF 뷰어 오픈·bbox 하이라이트**: M_12 Frontend 책임. 본 모듈은 `bbox`를 필드로 저장·반환만.
7. **임베딩 모델 다운로드**: 빌드 타임에 `assets/models/bge-m3/`에 배치. 런타임 `snapshot_download` 호출 금지(CLAUDE.md 오프라인 빌드 의무).
8. **min_score 런타임 자동 튜닝**: 사용자 벤치마크 기반 수동 조정(RISKS.md R-07). 본 스펙은 기본값 0.35와 `conf.yaml` 노출만 제공.
9. **문서 수준 집계·재정렬**(예: doc 단위 점수 합산 후 재정렬): V1은 chunk 단위 top_k 그대로 반환.
10. **다국어 쿼리 자동 판별**: BGE-M3는 다국어 모델이므로 언어 감지 없이 동일 파이프라인.

---

## 2. 요구사항 연결

| REQUIREMENTS.md 항목 | M_07 기여 |
|---|---|
| §0 완전 오프라인 / Windows 10/11 | `sentence-transformers` + `lancedb`는 순수 파이썬/네이티브 휠로 오프라인 동작. 네트워크 호출 0건. 모델은 `assets/models/bge-m3/`에 빌드 타임 배치. |
| §2.1 페이지·섹션·bbox 메타데이터 보존 | LanceDB 스키마에 `page`/`section`/`bbox`/`source_path` 필드 포함(§5.1). |
| §2.2 인용 제공(`문서명.pdf 12페이지, '예산 승인 절차' 섹션`) | `RagService.format_citation(hit)` 고정 한국어 포맷(§7). |
| §2.2 "답을 찾지 못했습니다" 정책(추측 금지) | `min_score=0.35` 미만 시 `RetrievalResult(hits=..., found=False, no_match_reason=...)` 반환(§6.3, ARCHITECTURE §3.2). |
| §8 임베딩 = BGE-M3 | `sentence-transformers`로 `BAAI/bge-m3` 로컬 로드. 1024차원 float32. |
| §9 메모리 예산 | BGE-M3 fp32 ~2.2 GB(ARCHITECTURE §6.1 표 행). int8 대안은 R-02 완화 방안(본 스펙 §8). |
| §9 응답 지연(RAG 경로 ≤ 300 ms on CPU) | 단일 쿼리 end-to-end(embed+search+format) p95 ≤ 700 ms 목표(§8). MILESTONES M_07 "평균 300ms 이하" 준수. |
| §9 외부 네트워크 호출 금지 | `HF_HUB_OFFLINE=1` 환경변수 전제, `local_files_only=True`. URL 기반 다운로드 코드 0. |
| §10 단일 사용자 | `lancedb.connect`는 파일 기반 embed. 락·쿼터 불필요. |

---

## 3. upstream 재사용 분석

### 3.1 분류: **NEW** (REUSE / EXTEND / DROP 모두 없음)

- `grep -r "rag\|vector\|lancedb\|bge\|embed\|RagService\|VectorStore\|Embedder" upstream/Open-LLM-VTuber/src/` 결과(§15 증적): 도메인 히트 **0건**. 음성 대화·TTS·Agent 프레임워크로 벡터 검색 코드를 **포함하지 않는다**. 히트 6건은 모두 주석/무관 단어(`sentence_divider.py` 이름 일부, MeloTTS 파일, config, `input_types.py`의 `ImageSource` 언급 등).
- upstream에 `RagService` / `VectorStore` / `Embedder` / LanceDB / sentence-transformers 호출 **없음**.
- 결론: 100% 신규 구현. EXTEND/DROP 대상 없음.

### 3.2 부분 REUSE도 없음

M_05b ToolRouter가 `CompositeToolExecutor`에서 upstream `format_tool_result` 등을 재사용하는 방식과 달리, 본 모듈은 upstream 함수 수준 재사용 경로도 없다.

---

## 4. 공개 API

모든 공개 타입·함수는 `src/vector_search/__init__.py`에서 re-export한다(§14 구조).
Python 3.12 타입 힌트(`list[X]`, `X | None`, 표준 `np.ndarray` 반환)로 작성.

### 4.1 `DocumentChunk` (M_06과 공유)

```python
# src/vector_search/types.py
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class DocumentChunk:
    """문서 청크. M_06 DocumentIngest가 생성하고 M_07이 저장·검색.

    `embedding` 벡터는 이 타입이 **아니라** 별도 `vectors: np.ndarray` 파라미터로
    `VectorStore.upsert(chunks, vectors)`에 전달된다. 이는 numpy 배열이
    frozen dataclass에 담기지 않는 Python 특성과 배치 임베딩 효율을 고려한 분리다.
    """

    doc_id: str                                    # SHA-256 of (source_path + mtime)
    doc_name: str                                  # 사용자 표시용 (basename)
    category: str | None                           # 상위 폴더명. None 허용
    page: int | None                               # PDF/PPTX; DOCX/HWPX/TXT/MD는 None
    section: str | None                            # HWPX 섹션명·MD 헤더·DOCX Heading
    chunk_id: str                                  # UUIDv4 문자열
    text: str                                      # 청크 본문(전처리 후, 빈 문자열 금지)
    bbox: tuple[float, float, float, float] | None # PDF만 (x0, y0, x1, y1). 그 외 None
    source_path: str                               # 절대 경로 (Windows 경로 가능)
```

#### 4.1.1 정의 위치 결정

`DocumentChunk`는 **`src/vector_search/types.py`에 1곳 정의**하고 M_06 DocumentIngest가 `from vector_search.types import DocumentChunk`로 import한다.

근거:
- M_07이 먼저 구현되고(MILESTONES Week 2), M_06이 나중에 구현된다(Week 8b, HOLD). 의존 방향: M_06 → M_07.
- 복제 정의는 필드 불일치로 인한 실버그 위험. 한 곳 정의가 안전.
- M_06의 `docs/MODULES.md` L196~L209 초안 정의와 필드 **완전 일치**(§15 비교표).

### 4.2 `SearchHit` (평면 dataclass — **경계 충돌 해소**)

```python
# src/vector_search/types.py
@dataclass(frozen=True)
class SearchHit:
    """VectorStore.search가 반환하는 단일 검색 결과.

    설계 결정: DocumentChunk를 중첩하지 않고 **필드를 평면으로 복제**한다(§15.2 경계 충돌 A).
    - doc_name / page / section / chunk_id / text / bbox / source_path를 최상위로 노출.
    - score(0..1 cosine similarity)를 추가.
    - embedding 벡터는 포함하지 않는다(직렬화·메모리 절감).

    근거:
    1. `src/tool_router/router.py:245~251`이 `hit.doc_name`, `hit.page`, `hit.section`,
       `hit.chunk_id`, `hit.text` 등 **평면 접근**을 이미 사용한다. `getattr(..., None)`의
       silent-mask 현상을 제거하려면 평면 필드가 정답.
    2. 중첩(`hit.chunk.doc_name`) 대비 JSON 직렬화가 단순.
    3. `DocumentChunk`의 embedding 책임과 분리되어 있어 `VectorStore`가 LanceDB row를
       직접 매핑하기 쉽다(Arrow record → SearchHit dataclass 1:1).
    """

    # --- DocumentChunk에서 복제 (embedding 제외, category 포함) ---
    doc_id: str
    doc_name: str
    category: str | None
    page: int | None
    section: str | None
    chunk_id: str
    text: str
    bbox: tuple[float, float, float, float] | None
    source_path: str

    # --- 검색 결과 고유 ---
    score: float   # cosine similarity 0..1 (정규화 후. §6.2)
```

`DocumentChunk`와 `SearchHit`의 관계를 **명시적**으로 유지하기 위해 `SearchHit.from_chunk(chunk, score)` 정적 생성 헬퍼를 제공(§14 `types.py`).

### 4.3 `RetrievalResult`

```python
# src/vector_search/types.py
@dataclass(frozen=True)
class RetrievalResult:
    """RagService.retrieve의 유일한 반환 타입."""

    hits: list[SearchHit]          # 항상 리스트. found=False여도 상위 top_k를 담는다(§6.3.2).
    found: bool                    # 최상위 hit score >= min_score
    no_match_reason: str | None    # found=False일 때 한국어 설명. found=True면 None.
```

### 4.4 예외 타입

```python
# src/vector_search/errors.py
class VectorSearchError(Exception):
    """M_07 공통 기본 예외."""

class EmbedderError(VectorSearchError):
    """BGE-M3 로드·추론 실패."""

class VectorStoreError(VectorSearchError):
    """LanceDB I/O·스키마 불일치·연결 실패."""

class RetrievalError(VectorSearchError):
    """RagService 상위 파사드에서 발생하는 조합 실패(예: embedder 결과 NaN)."""
```

> **원칙**: `RagService.retrieve`는 가능한 예외를 잡아 `RetrievalResult(found=False, no_match_reason="검색 중 오류: ...")`로 **변환하지 않는다**. 예외는 호출자(`ToolRouter._handle_search_docs`)가 `handler_exception`으로 변환한다(M_05b 스펙 §6, §9 표 "search_docs LanceDB I/O 실패" 경로와 일치).
> 단 **빈 쿼리**는 예외가 아닌 정상 경로의 "no match"로 처리(§6.3.1). `top_k <= 0`은 `ValueError`(§6.3.3).

### 4.5 `Embedder`

```python
# src/vector_search/embedder.py
import numpy as np

class Embedder:
    """BGE-M3 로컬 로드 + 배치 임베딩.

    동기 API로 확정한다. CPU 추론 자체가 blocking·CPU-bound이며, 호출자(RagService)가
    sync이므로 async 감싸기는 불필요.

    Args:
        model_dir: `assets/models/bge-m3/` 절대/상대 경로. sentence-transformers가 이
                   디렉토리에 `config.json`, `pytorch_model.bin` 또는 `model.safetensors`
                   등이 있다고 가정하고 `local_files_only=True`로 로드.
        device:    "cpu" | "cuda" | "auto". 기본 "cpu". "auto"는 torch.cuda.is_available()
                   기반. 런타임에 실패 시 "cpu" fallback + warning 로그.
        batch_size: embed_passages 내부 micro-batch 크기. 기본 32.
        normalize:  L2 정규화 여부. 기본 True (cosine=dot 등가).

    Raises:
        EmbedderError: 모델 로드 실패, 외부 네트워크 시도 탐지, config.json 누락.
    """

    def __init__(
        self,
        model_dir: str,
        device: str = "cpu",
        batch_size: int = 32,
        normalize: bool = True,
    ) -> None: ...

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        """N개 passage를 (N, 1024) float32 배열로 변환.

        - 빈 리스트 입력 → shape (0, 1024) float32 empty 배열 반환(에러 아님).
        - 각 text는 BGE-M3 공식 dense 모드로 임베딩(prefix 없음).
        - normalize=True면 L2 norm=1.0 (±1e-6). normalize=False면 원본 벡터 반환.
        - text 중 빈 문자열("")이 있으면 해당 행은 0 벡터가 아니라 " "(공백 1자)로
          치환 후 임베딩(sentence-transformers가 공문서를 거부하는 경우 대비).
          호출자가 빈 문자열을 보내지 않도록 해야 하나 방어적으로 처리.

        Raises:
            EmbedderError: 추론 실패(OOM, CUDA 에러 등). CPU fallback 시도 후에도 실패하면 raise.
        """

    def embed_query(self, text: str) -> np.ndarray:
        """단일 query → (1024,) float32 배열.

        BGE-M3 공식 dense 모드는 query/passage prefix 차등을 두지 않으므로 동일 경로.
        (공식 README: multi-functionality dense embedding은 query/passage 구분 없이
         동일 encode. sparse/colbert 모드는 V1에서 사용하지 않는다.)

        빈 문자열 또는 공백만 → " "(공백 1자)로 치환 후 임베딩(방어적).
        """
```

#### 4.5.1 오프라인 로드 확정

- 생성자 시작부에 `os.environ.setdefault("HF_HUB_OFFLINE", "1")` + `os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")` 강제.
- `SentenceTransformer(model_dir, device=device, local_files_only=True, cache_folder=None)`로 로드. `cache_folder=None` + `model_dir` 절대 경로로 HF 캐시 회피.
- 모델 디렉토리가 없거나 `config.json` 누락 → `EmbedderError("bge-m3 model not found at {model_dir}")` 기동 실패.

#### 4.5.2 Device 정책

- 기본 `"cpu"` — MIN 프로파일 기본. CPU embed 실측 목표 ≤ 300 ms/query(i7-12700, 512 token, fp32).
- `"auto"` — `torch.cuda.is_available() and torch.cuda.device_count() >= 1`이면 `cuda:0`, 아니면 `cpu`. CUDA 선택 후 첫 `embed_passages`가 실패하면 영구적으로 `cpu`로 강등 + `logger.warning`.
- `"cuda"` 명시 호출인데 CUDA 사용 불가 → `EmbedderError`. 사용자 의도 무시 금지.
- fp16 저장 가중치라도 `device="cpu"`면 자동 fp32 승격(sentence-transformers 기본 동작)—MILESTONES M_07 DoD 명시.

### 4.6 `VectorStore`

```python
# src/vector_search/store.py
import numpy as np
from .types import DocumentChunk, SearchHit

class VectorStore:
    """LanceDB 기반 청크 저장소.

    동기 API로 확정. LanceDB의 `connect` 및 `add`/`merge_insert`/`search`는 sync 메서드이며,
    본 모듈은 async 래핑을 하지 않는다. 호출자(RagService)는 sync, ToolRouter가
    run_in_executor로 외부 async에 어댑팅한다(§15.1 경계 충돌 B).

    Args:
        db_path: LanceDB 디렉토리 경로. 부재 시 자동 생성. 단일 프로세스만 접근.
        table:   테이블명. 기본 "chunks".

    Raises:
        VectorStoreError: db_path 접근 실패, 기존 테이블의 vector 차원이 1024가 아닐 때.
    """

    def __init__(self, db_path: str, table: str = "chunks") -> None: ...

    def upsert(
        self,
        chunks: list[DocumentChunk],
        vectors: np.ndarray,   # shape (len(chunks), 1024) float32
    ) -> int:
        """chunk_id 기준 멱등 upsert.

        - len(chunks) != vectors.shape[0] → VectorStoreError.
        - vectors.shape[1] != 1024 → VectorStoreError.
        - vectors.dtype != float32 → 내부에서 np.float32로 cast (warning 로그 없이 허용).
        - 빈 입력 → 0 반환(에러 아님).

        구현: LanceDB `merge_insert(on="chunk_id").when_matched_update_all()
              .when_not_matched_insert_all().execute(df)` (§5.3).

        Returns:
            실제 written row 수(신규 insert + 업데이트 합). LanceDB의 merge_insert 통계 활용.

        Raises:
            VectorStoreError: Arrow 스키마 충돌, 디스크 쓰기 실패.
        """

    def search(
        self,
        query_vec: np.ndarray,    # shape (1024,) float32
        top_k: int = 8,
        category: str | None = None,
    ) -> list[SearchHit]:
        """코사인 유사도 ANN 검색.

        - query_vec shape != (1024,) → VectorStoreError.
        - top_k <= 0 → ValueError.
        - top_k > 50 → 상한 50으로 clamp + warning 로그(M_05b schema maximum=20과 정합,
          단 RAG 내부에서 M_11/테스트가 더 많이 요청할 여지를 위해 50으로 설정).
        - category 지정 시 `where("category = ?")` LanceDB 파라미터 바인딩(§6.2.2).
          LanceDB는 prepared-statement 수준 파라미터화가 없지만 LanceDB SQL filter는
          문자열 리터럴을 **quote-escape**해 삽입하므로, 본 모듈은 category 값을
          단순 quote+escape(`'` → `''`)로 삽입. (§11 A-3 SQL-like 공격 테스트 커버).

        반환: cosine similarity 내림차순 정렬된 SearchHit 리스트. 결과 0건 → [].

        점수 정규화: §6.2에서 계산.
        """

    def delete_by_doc_id(self, doc_id: str) -> int:
        """특정 문서의 모든 청크 삭제.

        M_06의 재-ingest 시 호출. `ingest_directory`가 동일 source_path를 다시 읽을 때
        기존 청크를 완전 삭제 후 새 청크를 upsert하는 2단계 전략의 전반부.

        Returns:
            삭제된 row 수.

        Raises:
            VectorStoreError: 삭제 실패. doc_id가 존재하지 않으면 예외 아닌 0 반환.
        """
```

### 4.7 `RagService`

```python
# src/vector_search/rag.py
from .embedder import Embedder
from .store import VectorStore
from .types import RetrievalResult, SearchHit

class RagService:
    """Embedder + VectorStore 파사드. sync API.

    Args:
        embedder:   Embedder 인스턴스.
        store:      VectorStore 인스턴스.
        min_score:  "관련 없음" 판정 임계값. 기본 0.35 (MILESTONES M_07 L83).
                    conf.yaml의 `rag.min_score`로 덮어쓸 수 있다.
        top_k_max:  retrieve 호출의 top_k 상한. 기본 20. (JSON Schema와 일치)
    """

    def __init__(
        self,
        embedder: Embedder,
        store: VectorStore,
        min_score: float = 0.35,
        top_k_max: int = 20,
    ) -> None: ...

    def retrieve(
        self,
        query: str,
        top_k: int = 8,
        category: str | None = None,
    ) -> RetrievalResult:
        """쿼리를 임베딩해 VectorStore를 검색하고 RetrievalResult를 반환.

        **sync 함수로 확정**. 호출자(ToolRouter._handle_search_docs)가
        `run_in_executor(None, lambda: self._rag.retrieve(query, top_k, category))`로
        외부 async 경계에 어댑팅한다(§15.1 경계 충돌 B).

        흐름:
          1. query.strip() == "" → 빈 hits + found=False + no_match_reason="쿼리가 비어있습니다"
             (EMBEDDER_CALL_COUNT=0; 캐시).
          2. top_k <= 0 → raise ValueError("top_k must be >= 1").
          3. top_k > top_k_max → clamp(top_k = top_k_max) + warning 로그.
          4. query_vec = embedder.embed_query(query).
          5. hits = store.search(query_vec, top_k=top_k, category=category).
          6. found = len(hits) > 0 and hits[0].score >= min_score.
          7. found=False면 no_match_reason 생성(§6.3.2).

        반환 계약 (found=False인 경우의 hits 유지 정책):
          - found=False여도 hits는 **그대로 top_k** 채워 반환한다(단, 0건일 수도 있음).
          - 근거: ToolRouter._handle_search_docs(L240~L253)는 hits를 순회하며 페이로드를
                   구성한다. LLM이 "낮은 점수이지만 참고는 했다"는 신호를 가질 수 있도록
                   hits를 비우지 않는다. 단 LLM은 `found=False` + `no_match_reason`을 보고
                   "등록된 문서에서 답을 찾지 못했습니다"로 응답하도록 M_05 프롬프트가
                   지시한다(M_05 스펙 범위). 본 모듈은 **양쪽 정보를 모두 제공**한다.
                   (REQUIREMENTS.md §2.2 "추측 금지"는 LLM 프롬프트가 강제, 본 모듈은
                   no_match_reason을 제공해 근거를 넘긴다.)
        """

    def format_citation(self, hit: SearchHit) -> str:
        """인용 문자열을 한국어 고정 포맷으로 생성. §7 참조."""
```

---

## 5. 데이터 모델 / LanceDB 스키마

### 5.1 PyArrow 스키마 (V1)

```python
# src/vector_search/schema.py
import pyarrow as pa

EMBEDDING_DIM: int = 1024  # BGE-M3 dense

CHUNKS_SCHEMA: pa.Schema = pa.schema([
    pa.field("doc_id",       pa.string(), nullable=False),
    pa.field("doc_name",     pa.string(), nullable=False),
    pa.field("category",     pa.string(), nullable=True),
    pa.field("page",         pa.int32(),  nullable=True),
    pa.field("section",      pa.string(), nullable=True),
    pa.field("chunk_id",     pa.string(), nullable=False),  # PK 역할 (멱등 키)
    pa.field("text",         pa.string(), nullable=False),
    pa.field("bbox",         pa.list_(pa.float32(), 4), nullable=True),  # [x0,y0,x1,y1]
    pa.field("source_path",  pa.string(), nullable=False),
    pa.field("vector",       pa.list_(pa.float32(), EMBEDDING_DIM), nullable=False),
])
```

#### 5.1.1 필드 주석

| 필드 | PyArrow 타입 | 기원 | 인덱스 |
|---|---|---|---|
| `doc_id` | `string` | M_06이 SHA-256(path+mtime)로 생성 | `delete_by_doc_id` 경로에서 스캔 |
| `doc_name` | `string` | basename | 미인덱스 |
| `category` | `string?` | 폴더명, nullable | where-filter 스캔(§6.2.2) |
| `page` | `int32?` | PDF/PPTX만 | 미인덱스 |
| `section` | `string?` | HWPX/MD/DOCX 헤더 | 미인덱스 |
| `chunk_id` | `string` | UUIDv4. **멱등 키** | merge_insert 매칭 키 |
| `text` | `string` | 청크 본문 | 미인덱스 |
| `bbox` | `list<float32, 4>?` | PDF 단락 박스 | 미인덱스 |
| `source_path` | `string` | 절대 경로 | 미인덱스 |
| `vector` | `list<float32, 1024>` | BGE-M3 출력 | **ANN 인덱스(§5.2)** |

### 5.2 인덱스 결정

- **V1: brute-force cosine** (인덱스 미생성).
  - 근거: 예상 최대 1만 청크(ARCHITECTURE §6.1 "1만 청크 × 1024dim × 4B ≈ 40MB"). 1만 벡터 brute-force는 CPU에서 p95 ≤ 50 ms(LanceDB 내부 SIMD).
  - IVF_PQ 인덱스는 추가 학습 단계·build 시간·품질 손실 trade-off 발생. 1만 스케일에선 불필요.
- **V2(미래, 본 스펙 범위 밖)**: 청크 ≥ 10만 시 `create_index(metric="cosine", index_type="IVF_PQ", num_partitions=N)` 도입. RISKS에 추가할 항목 없음(현 스케일에서 미발생).
- 본 모듈은 brute-force만 사용하지만, `VectorStore.search`의 LanceDB 호출은 `.metric("cosine")`을 명시해 향후 인덱스 전환과 API 호환을 유지.

### 5.3 `upsert` 의미론 — `merge_insert` 채택

```python
# 의사코드
table.merge_insert("chunk_id") \
     .when_matched_update_all() \
     .when_not_matched_insert_all() \
     .execute(pyarrow_table)
```

**채택 근거** (대안 비교):
1. **`delete + insert`**: 같은 효과지만 2회 I/O, 트랜잭션 보장 LanceDB에 없음 → 부분 실패 리스크.
2. **`add`(insert만)**: 동일 `chunk_id` 중복 행이 누적 → 검색 결과에 중복 등장. V1 금지.
3. **`merge_insert`**: 단일 호출로 upsert 의미론을 제공하며 LanceDB 공식 경로. 채택.

`delete_by_doc_id`는 별도 호출: `table.delete(f"doc_id = '{doc_id_escaped}'")`. 재-ingest 시 M_06이 `delete_by_doc_id` → `upsert` 2단계로 수행(§4.6 후반).

### 5.4 테이블 생성 조건

- `VectorStore.__init__`:
  1. `db = lancedb.connect(db_path)`.
  2. 테이블 존재 여부 확인: `if table_name in db.table_names():`.
  3. 존재하면 열고 **스키마 검증**: 기존 스키마의 `vector` 필드가 `list<float32, 1024>`이 아니면 `VectorStoreError("schema mismatch: migration required")` + 로그 에러. **자동 마이그레이션하지 않음**(사용자가 DB 디렉토리를 수동 재생성).
  4. 없으면 `db.create_table(name, schema=CHUNKS_SCHEMA, mode="create")`.
- 빈 테이블은 허용. `search` 호출 시 결과 0건 반환.

---

## 6. 동작 상세

### 6.1 Embedder 동작 순서

1. `__init__`: 오프라인 환경변수 설정 → `SentenceTransformer(model_dir, device, local_files_only=True)`.
2. `embed_passages(texts)`:
   - 빈 리스트 → `np.empty((0, 1024), dtype=np.float32)`.
   - 빈 문자열은 `" "`(공백 1자)로 치환.
   - `encode(texts, batch_size=self.batch_size, normalize_embeddings=self.normalize, convert_to_numpy=True)` 호출 결과가 fp16/fp32 어떤 dtype이어도 `.astype(np.float32, copy=False)`로 통일.
   - NaN/Inf 검사: `np.isfinite(output).all()`이 False면 `EmbedderError("embedder produced NaN/Inf")`.
3. `embed_query(text)`: `embed_passages([text])[0]` 경로로 위임. 반환 shape `(1024,)`.

### 6.2 VectorStore.search 동작 순서

1. 입력 검증: `query_vec.shape == (1024,)`, `top_k > 0`.
2. `top_k > 50` → `top_k = 50` + warning 로그.
3. LanceDB 쿼리 빌드:
   ```python
   q = table.search(query_vec).metric("cosine").limit(top_k)
   if category is not None:
       q = q.where(f"category = '{category.replace(chr(39), chr(39)+chr(39))}'")
   df = q.to_pandas()   # 또는 to_list() 경로
   ```
4. 결과 row 순회 → `SearchHit.from_chunk_row(row)` 변환 후 list 반환.

#### 6.2.1 점수 정규화 수식

LanceDB `.metric("cosine")`는 **cosine distance**(0=동일, 2=반대)를 컬럼 `_distance`로 반환한다. cosine similarity로 변환:

```
similarity = 1.0 - (distance / 2.0)
```

- 완전 일치 → distance 0 → similarity 1.0.
- 수직 → distance 1 → similarity 0.5.
- 완전 반대 → distance 2 → similarity 0.0.

score는 `[0.0, 1.0]` 범위로 clamp(부동소수 오차 대비): `score = max(0.0, min(1.0, 1.0 - distance/2.0))`.

> **주의**: L2 정규화된 벡터끼리의 dot product는 `1 - (dist_L2^2 / 2)`로 cosine sim과 등가이지만, LanceDB `.metric("cosine")`이 직접 cosine distance를 돌려주므로 위 수식이 정답이다. 실제 구현 시 LanceDB 버전 업에 따라 컬럼명/스케일 변동 가능 → 단위 테스트로 검증(§11 N-6).

#### 6.2.2 category 필터 파라미터화

LanceDB는 SQL-like WHERE를 지원하나 bind parameter API가 V1 시점에 제한적이다(특히 파이썬 바인딩). 본 모듈은 다음 방어 규칙으로 SQL-like 인젝션을 차단한다:

1. `category` 값의 single quote(`'`)를 `''`로 double-escape.
2. `category` 값에 ASCII 제어 문자(0x00~0x1F) 포함 시 `VectorStoreError("invalid category")`.
3. category 최대 길이 100자(M_05b JSON Schema와 동일).
4. 이 정책은 §11 A-3 테스트로 회귀 검증.

### 6.3 RagService.retrieve 경로

#### 6.3.1 빈 쿼리 처리

```python
if not query or not query.strip():
    return RetrievalResult(
        hits=[],
        found=False,
        no_match_reason="쿼리가 비어있습니다",
    )
```

Embedder 호출 없이 즉시 반환. `logger.info("empty query received")`.

#### 6.3.2 no_match_reason 포맷

- hits가 0건: `no_match_reason = "등록된 문서에서 관련 내용을 찾지 못했습니다"`.
- hits가 있으나 최상위 score < min_score:
  ```
  no_match_reason = (
      f"등록된 문서에서 관련 내용을 찾지 못했습니다 "
      f"(최고 유사도 {top_score:.2f} < {min_score:.2f})"
  )
  ```
- hits가 있고 최상위 score >= min_score → `no_match_reason = None`, `found=True`.

포맷은 **M_05 프롬프트가 읽는 문자열**이므로 변경 시 M_05와 동기화 CR 필요.

#### 6.3.3 `top_k` 검증

- `top_k <= 0` → `raise ValueError("top_k must be >= 1")`. ToolRouter의 JSON Schema가 `minimum: 1`로 이미 차단하지만, 본 모듈 단독 호출 경로(테스트, M_06 디버그) 대비 방어.
- `top_k > top_k_max`(기본 20) → `top_k = top_k_max` clamp + `logger.warning`.

### 6.4 `format_citation(hit: SearchHit) -> str`

고정 한국어 포맷. §7에 전문.

---

## 7. 인용(citation) 포매터 사양

### 7.1 기본 포맷

입력: `SearchHit` (page, section 조합). backtick은 파이썬 source에서 escape.

| page | section | 반환 문자열 예 |
|---|---|---|
| 12 | `"예산 승인 절차"` | `` `예산지침.pdf` 12페이지, '예산 승인 절차' 섹션 `` |
| 12 | None | `` `예산지침.pdf` 12페이지 `` |
| None | `"1. 서론"` | `` `회의록.docx` '1. 서론' 섹션 `` |
| None | None | `` `메모.txt` `` |

### 7.2 구현 규칙

```python
def format_citation(self, hit: SearchHit) -> str:
    doc = f"`{hit.doc_name}`"
    parts = [doc]
    if hit.page is not None:
        parts.append(f"{hit.page}페이지")
    if hit.section:
        # section 값에 single quote가 있으면 그대로 둔다(사용자 데이터 보존).
        # backtick은 우리가 부여한 doc 경계 심볼이므로 section에는 사용되지 않는다.
        parts.append(f"'{hit.section}' 섹션")
    # 연결: 첫 요소(doc) 뒤에는 공백, 이후는 ", "
    if len(parts) == 1:
        return parts[0]
    return parts[0] + " " + ", ".join(parts[1:])
```

### 7.3 문자열 직렬화 계약

- `ensure_ascii=False` JSON에 그대로 실린다(한국어 유지).
- 길이 상한 없음(문서명·섹션명은 사용자 데이터).
- backtick/single quote는 Gemma 프롬프트 혼란을 주지 않는 것으로 가정(10건 FC 스파이크에서 문제 없음).

---

## 8. 성능·메모리 예산

### 8.1 성능 목표

| 항목 | 목표 | 근거 |
|---|---|---|
| `Embedder.__init__` | CPU 5~10 s, 1회성 | fp32 2.2GB 파일 mmap. 기동 시 상주. |
| `Embedder.embed_query` | p95 ≤ 300 ms (CPU, i7-12700) | MILESTONES M_07. |
| `Embedder.embed_passages(32)` | p95 ≤ 3 s | batch 32, 각 텍스트 512 token. M_06 ingest 경로. |
| `VectorStore.search` (1만 청크, brute-force) | p95 ≤ 50 ms | ARCHITECTURE §6.1. LanceDB SIMD. |
| `VectorStore.upsert` (청크 100건) | p95 ≤ 200 ms | merge_insert 1회 flush. |
| **`RagService.retrieve` end-to-end** | p95 ≤ 700 ms (CPU) | embed_query(300) + search(50) + 정규화/포매팅(수십 ms) + python overhead |
| MILESTONES M_07 "평균 300ms 이하" | 준수 | CPU 평균은 ~500 ms 이내 관측 예상. p50 기준. |

### 8.2 메모리 예산

| 컴포넌트 | 상주 RSS | 주석 |
|---|---|---|
| BGE-M3 fp32 가중치 | ~2.2 GB | ARCHITECTURE §6.1 일치 |
| LanceDB table (1만 청크) | ~40 MB 본체 + ~50 MB OS 버퍼 | 파일 mmap |
| PyArrow/Pandas 중간 버퍼 | ≤ 100 MB 피크 | 검색 결과 DataFrame 변환 순간 |
| Python + sentence-transformers 라이브러리 | ~300 MB | 토크나이저, torch 텐서 캐시 |

**합계 피크**: ~2.7 GB. ARCHITECTURE §6.1의 "BGE-M3 2.2 GB + LanceDB 300 MB" 범위 내.

### 8.3 int8 대안(R-02 완화 경로)

- 본 스펙 범위는 fp32 기본. **int8 대안 API 서피스만 남기고 V1은 fp32 고정**.
- int8 경로 도입 시(`scripts/bundle_deps.sh`가 `bge-m3-int8/`도 수집) `Embedder(model_dir="...bge-m3-int8/")`로 호출만 바꾸면 된다 — 본 스펙은 추가 플래그를 도입하지 않는다(복잡성 증가 회피).
- int8 채택은 **별도 CR**로 사용자 승인 후 진행. 품질 측정(RISKS R-07 벤치마크)이 전제.

### 8.4 동시성 / 스레드 안전성

- `Embedder` — `SentenceTransformer.encode`는 torch forward로 내부 GIL-release. 다중 executor worker에서 동시 호출해도 순차화되며 정확성 유지. 본 모듈은 별도 lock 없음.
- `VectorStore` — LanceDB는 단일 writer 가정. V1은 단일 프로세스 단일 사용자(REQUIREMENTS §10). 별도 lock 없음. 단 M_06의 `ingest_directory`가 동시에 `upsert`를 호출할 경우 M_06이 순차화(본 모듈 책임 아님).

---

## 9. 에러 처리 정책

| 상황 | 반응 | 예외 raise? | 로그 |
|---|---|---|---|
| 모델 경로 없음/손상 | `EmbedderError` | yes (init) | ERROR |
| `embed_*` 중 NaN/Inf 출력 | `EmbedderError` | yes | ERROR |
| `device="cuda"` 요청이나 CUDA 불가 | `EmbedderError` | yes (init) | ERROR |
| `device="auto"`에서 CUDA forward 1회 실패 | CPU fallback, 재시도 | no | WARNING |
| `db_path` 접근 불가 | `VectorStoreError` | yes (init) | ERROR |
| 기존 테이블 vector 차원 != 1024 | `VectorStoreError("schema mismatch: migration required")` | yes (init) | ERROR |
| `upsert` chunks/vectors 길이/차원 불일치 | `VectorStoreError` | yes | ERROR |
| `upsert` 빈 입력 | 0 반환 | no | DEBUG |
| `search` query_vec shape != (1024,) | `VectorStoreError` | yes | ERROR |
| `search` top_k <= 0 | `ValueError` | yes | WARNING |
| `search` top_k > 50 | clamp + warning | no | WARNING |
| `search` category에 제어 문자 | `VectorStoreError("invalid category")` | yes | WARNING |
| `search` 결과 0건 | `[]` 반환 | no | DEBUG |
| `RagService.retrieve` 빈 쿼리 | `RetrievalResult(found=False, no_match_reason="쿼리가 비어있습니다")` | no | INFO |
| `RagService.retrieve` top_k <= 0 | `ValueError` | yes | WARNING |
| `RagService.retrieve` 최상위 score < min_score | `found=False` + no_match_reason | no | INFO |
| `RagService.retrieve` embedder 예외 | 상위로 전파 (ToolRouter가 `handler_exception`으로 변환) | yes | ERROR |
| `delete_by_doc_id` doc_id 미존재 | 0 반환 | no | DEBUG |

### 9.1 원칙

- `RagService.retrieve`는 **"검색 시도 후 결과 없음"과 "입력 문제로 검색 불가"를 구분한다**. 전자는 정상 경로의 `RetrievalResult(found=False, ...)`, 후자는 `ValueError` 혹은 하위 예외.
- 런타임 I/O 실패는 잡지 않고 상위로 던진다. ToolRouter의 `handler_exception` 경로가 이를 `ToolResult(ok=False, error_code="handler_exception")`으로 변환(M_05b §9 표와 정합).

---

## 10. 설정(conf.yaml) 노출

M_01 AppCore가 YAML을 읽어 본 모듈을 생성한다. 키 설계는 M_01 스펙 범위에서 확정되지만 본 스펙은 **필요 키 목록**을 고정한다:

```yaml
rag:
  embedder_model_dir: "assets/models/bge-m3"   # required
  device: "cpu"                                 # "cpu" | "cuda" | "auto"
  db_path: "data/vector_store"                  # required
  table: "chunks"
  min_score: 0.35                               # 0.0 ~ 1.0
  top_k_default: 8                              # JSON Schema default와 정합
  top_k_max: 20                                 # M_05b schema maximum과 정합
```

- `device: "auto"`는 개발 머신에 CUDA가 있을 때만 권장. 배포 기본은 `"cpu"`.
- `min_score`는 RISKS R-07에 따라 사용자 인스턴스 튜닝. 본 스펙은 기본값만.

---

## 11. 테스트 케이스

경로: `tests/vector_search/`. `pytest-asyncio`는 불필요(모든 API sync). LanceDB는 `tmp_path` 실 인스턴스.

### 11.1 공통 픽스처

```text
conftest.py:
    - tmp_db_path(tmp_path) fixture: tmp_path / "lancedb_v1"
    - FakeEmbedder:
        고정 규칙으로 (N, 1024) 반환. 예: text 해시 기반 random state로 결정론적 벡터.
        L2 정규화 포함. BGE-M3 실로드를 회피해 테스트 시간을 단축.
    - sample_chunks(N=5): DocumentChunk 5개 더미.
    - real_embedder_marker: @pytest.mark.slow — 실제 BGE-M3 로드 필요 테스트만.
```

**근거**: BGE-M3 실모델 로드는 CI에서 2.2 GB mmap + 5~10 s 로드로 비효율. `Embedder` 자체 동작은 별도 `test_embedder_real.py`에서 `@pytest.mark.slow`로 1건만 실행.

### 11.2 정상 케이스 (≥ 5)

**N-1. `VectorStore.upsert` → `search` round-trip**
- FakeEmbedder로 5개 chunk 임베딩 → upsert(5) → search(query_vec=동일 embedding[0], top_k=3).
- 검증: 반환 3건, 첫 hit.chunk_id == chunks[0].chunk_id, score ≥ 0.99.

**N-2. `RagService.retrieve` 성공 케이스 (found=True)**
- FakeEmbedder가 query와 chunk[0]을 동일 벡터로 생성하도록 fixture 구성.
- 입력: `retrieve("승인 절차", top_k=3)`.
- 검증: `found=True`, `no_match_reason is None`, `len(hits)==3`, `hits[0].score >= 0.35`.

**N-3. `format_citation` 전 케이스**
- `(page=12, section="예산 승인 절차")` → `` `doc.pdf` 12페이지, '예산 승인 절차' 섹션 ``.
- `(page=12, section=None)` → `` `doc.pdf` 12페이지 ``.
- `(page=None, section="1. 서론")` → `` `doc.docx` '1. 서론' 섹션 ``.
- `(page=None, section=None)` → `` `doc.txt` ``.

**N-4. `delete_by_doc_id` 멱등**
- 동일 doc_id의 청크 3개 upsert → delete_by_doc_id → 0건 확인. 재호출해도 에러 없이 0 반환.

**N-5. `category` 필터**
- chunks 중 3개는 category="규정", 2개는 "매뉴얼" upsert.
- `search(q, top_k=5, category="규정")` → hits 전원 `category=="규정"`.

**N-6. 점수 정규화 수식 검증**
- LanceDB가 반환한 `_distance=0.0` 케이스에서 score=1.0, `_distance=1.0`에서 score=0.5, `_distance=2.0`에서 score=0.0인지 검증(FakeEmbedder로 제어된 벡터 주입).

**N-7. `Embedder.embed_passages` 빈 리스트**
- `embed_passages([])` → shape `(0, 1024)` float32 배열 반환.

### 11.3 엣지 케이스 (≥ 5)

**E-1. 빈 쿼리 → no match**
- `retrieve("")` → `found=False`, `no_match_reason=="쿼리가 비어있습니다"`, Embedder 호출 0회(mock assert).

**E-2. 공백만 쿼리 → no match**
- `retrieve("   \n\t  ")` → E-1과 동일.

**E-3. 최상위 score가 min_score 바로 아래 → found=False, hits 유지**
- FakeEmbedder로 top score=0.34가 되도록 조정.
- 검증: `found=False`, `no_match_reason` 문자열에 `"0.34"`와 `"0.35"` 포함. `len(hits) == top_k`(비지 않음).

**E-4. top_k=1 경계**
- `retrieve("q", top_k=1)` → hits 1건만.

**E-5. top_k=20(상한) / top_k=21(clamp)**
- top_k=20 정상. top_k=21 → warning 로그 + 실제 top_k=20 적용. (top_k_max=20 기본)

**E-6. `upsert` chunks=[]**
- `upsert([], np.empty((0,1024)))` → 0 반환, 테이블 변화 없음.

**E-7. category에 한글·특수문자 정상값**
- `search(q, category="규정 v2-2024")` → 성공. (single quote·제어문자 없음)

**E-8. bbox None vs 있음 라운드트립**
- PDF 청크(bbox 있음)와 TXT 청크(bbox None) upsert → search → 각 SearchHit.bbox가 원본과 일치(None 포함).

### 11.4 적대적 케이스 (≥ 3)

**A-1. 동일 `chunk_id` 중복 upsert(멱등)**
- 같은 `chunk_id`로 `text`가 바뀐 chunk를 두 번 upsert.
- 검증: 테이블 내 row 수 불변(1), `search` 결과 text는 두 번째 값. `merge_insert` 동작 확인.

**A-2. `upsert` vectors shape 불일치**
- chunks 3개, vectors shape `(3, 512)` → `VectorStoreError`. 테이블 변화 없음.
- chunks 3개, vectors shape `(2, 1024)` → `VectorStoreError`.

**A-3. category에 SQL-like 주입 문자열**
- `search(q, category="' OR 1=1 --")` → 테스트 두 가지 중 하나가 성립해야 함:
  1. (안전) `where` 절이 escape되어 결과 0건(해당 category 없음).
  2. (정책) `VectorStoreError("invalid category")` raise(제어문자 포함 시).
- 검증: 어떤 경우에도 다른 category의 row가 반환되지 않음. 기존 테이블이 훼손되지 않음.

**A-4. `query_vec` shape 공격**
- `store.search(np.zeros((1024, 1024)), top_k=5)` → `VectorStoreError` (shape 불일치).
- `store.search(np.zeros(1023), top_k=5)` → `VectorStoreError`.

**A-5. 매우 긴 쿼리**
- `query = "가" * 10_000` (BGE-M3 max 8192 token을 초과).
- 검증: `retrieve`가 예외 없이 완료(sentence-transformers가 max_length로 truncate). `found` 값은 데이터에 따름.

**A-6. NaN/Inf 벡터 삽입 방어**
- Embedder가 반환한 벡터에 NaN 주입(monkeypatch) → `EmbedderError` raise. `retrieve`가 해당 예외를 상위로 전파.

### 11.5 실모델 smoke 테스트(별도, `@pytest.mark.slow`)

**S-1. 실 BGE-M3 로드 + embed_query shape**
- `Embedder(model_dir="assets/models/bge-m3", device="cpu")` 로드.
- `embed_query("안녕하세요")` → shape `(1024,)`, dtype float32, L2 norm ≈ 1.0.
- CI 기본 제외(`-m "not slow"`). 실행 조건: 모델 파일 존재.

---

## 12. Definition of Done

### 12.1 공통 (CLAUDE.md "산출물 체크리스트")

- [ ] `specs/M_07_VectorSearch_SPEC.md` (본 파일, 사용자 승인).
- [ ] `src/vector_search/` 구현 (§14 구조).
- [ ] `tests/vector_search/` 정상 ≥ 5, 엣지 ≥ 5, 적대적 ≥ 3.
- [ ] `ruff format .`, `ruff check .`, `mypy src/vector_search`, `pytest tests/vector_search -v` 모두 통과.
- [ ] `reviews/M_07_VectorSearch_REVIEW.md` Critic PASS.
- [ ] `docs/MODULES.md` M_07 상태 `🔲 TODO` → `✅ DONE`.

### 12.2 M_07 고유 DoD (MILESTONES M_07 L77~L86 재확인)

- [ ] `Embedder.embed_passages(["안녕하세요"]).shape == (1, 1024)` & `dtype == np.float32`.
- [ ] `VectorStore.upsert` → `search` 왕복이 동일 `doc_id` 청크를 상위 3위 내에서 재현(N-1).
- [ ] `RagService.retrieve(q)`가 `min_score=0.35` 미만일 때 `found=False`(E-3).
- [ ] 단일 쿼리 검색 CPU 평균 ≤ 300 ms(S-1 실측 로깅). p95 ≤ 700 ms end-to-end.
- [ ] LanceDB 스키마: `vector`(1024 float32), `doc_id`, `doc_name`, `category`, `page`, `section`, `chunk_id`, `text`, `bbox`, `source_path` 전부 존재(§5.1).
- [ ] fp16 저장 모델을 `device="cpu"`에서 로드할 때 자동 fp32 승격(S-1 선택적).

### 12.3 ToolRouter 호환성 (경계 계약)

- [ ] `SearchHit`의 평면 필드가 `src/tool_router/router.py:245~251`의 `getattr(hit, "doc_name", None)` 등 접근 경로와 **정확히 매칭**. 실제로 `getattr(..., None)`이 아닌 직접 attribute 접근도 성공.
- [ ] `RagService.retrieve`가 sync 함수. ToolRouter의 `run_in_executor(None, lambda: self._rag.retrieve(...))` 호출이 동작.
- [ ] `format_citation(hit)`이 한국어 문자열 반환. `ToolResult.payload["hits"][i]["citation"]`에 그대로 실림.
- [ ] `retrieval.found` / `retrieval.hits` / `retrieval.no_match_reason` 3속성 존재.
- [ ] ToolRouter 통합 테스트(M_05b tests/tool_router/test_dispatch_normal.py N-3, E-7)가 `FakeRagService` 대신 **본 모듈 실제 RagService(FakeEmbedder + real LanceDB on tmp_path)**로도 통과.

### 12.4 의존성·빌드

- [ ] `pyproject.toml`에 의존성 추가: `sentence-transformers>=3.0,<5`, `lancedb>=0.10,<1`, `pyarrow>=15.0,<19`, `numpy>=1.26,<3`. 추가 사유를 커밋 메시지에 기록.
- [ ] `scripts/bundle_deps.sh`에 위 4종 wheel 다운로드 블록 추가. `huggingface-cli download BAAI/bge-m3 --local-dir assets/models/bge-m3`도 추가.
- [ ] 런타임 네트워크 호출 0건. `grep -r "http\|https\|snapshot_download\|HfApi" src/vector_search/` 결과 없음.

### 12.5 문서 동기화

- [ ] `docs/MODULES.md` M_07 블록의 **`SearchHit` 정의를 평면 dataclass로 수정**(초안의 `chunk: DocumentChunk` 중첩을 평면 필드로 교체). `async def retrieve` → `def retrieve`로 정정.
- [ ] M_06 스펙 작성자(HOLD 해제 시)는 `DocumentChunk`를 **복제 정의하지 않고** `from vector_search.types import DocumentChunk` 지시. 본 스펙 §4.1.1 메모 참조.
- [ ] `docs/RISKS.md` R-07에 "인스턴스 벤치마크 단계 포함(M_07 DoD §12.2)" 체크박스 확인.

### 12.6 무결성

- [ ] `upstream/Open-LLM-VTuber/**` git diff 빈 상태.
- [ ] 본 모듈이 `rag.min_score`를 런타임 자동 조정하지 않음(사용자 튜닝 훅만 제공).
- [ ] `Embedder` 초기화 시 `HF_HUB_OFFLINE=1` 등 오프라인 환경변수 설정 확인.

---

## 13. 의존성

### 13.1 신규 Python 패키지

| 패키지 | 버전 핀 | 용도 | 오프라인 번들 |
|---|---|---|---|
| `sentence-transformers` | `>=3.0,<5` | BGE-M3 로드·encode. transformers·torch 전이 | 핵심 |
| `lancedb` | `>=0.10,<1` | 파일 기반 벡터 DB | 핵심 |
| `pyarrow` | `>=15.0,<19` | LanceDB 스키마/배치 변환 | 핵심 |
| `numpy` | `>=1.26,<3` | 벡터 배열 | upstream이 이미 요구 가능성 높음(확인 후 추가 여부 결정) |
| `torch` | 기존(pyproject에 있음) | sentence-transformers 런타임 | 이미 있음 |
| `transformers` | sentence-transformers 전이 | 토크나이저 | sentence-transformers가 pin |

### 13.2 모델 파일

- `assets/models/bge-m3/` — `config.json`, `tokenizer.json`, `sentencepiece.bpe.model`, `pytorch_model.bin` 또는 `model.safetensors`. 빌드 타임 `huggingface-cli download BAAI/bge-m3`로 수집(bundle_deps.sh에 추가).
- 약 2.2 GB. git 커밋 금지(`.gitignore` 확장 필요 시 M_07 builder가 추가).

### 13.3 이미 있는 Python 표준 라이브러리

- `os`, `pathlib`, `logging`, `dataclasses`, `hashlib`, `uuid`(M_06이 생성하지만 본 모듈은 사용 안 함), `threading` 없음(단일 사용자).

### 13.4 개발 의존성

- `pytest`, `pytest-cov` 기존. 신규 없음.

---

## 14. 디렉토리 구조

```
src/vector_search/
├── __init__.py          # 공개 심볼 re-export
│                        #   from .types import DocumentChunk, SearchHit, RetrievalResult
│                        #   from .errors import (VectorSearchError, EmbedderError,
│                        #                        VectorStoreError, RetrievalError)
│                        #   from .embedder import Embedder
│                        #   from .store import VectorStore
│                        #   from .rag import RagService
├── types.py             # DocumentChunk, SearchHit, RetrievalResult + SearchHit.from_chunk
├── errors.py            # 예외 4종
├── schema.py            # CHUNKS_SCHEMA (pa.Schema), EMBEDDING_DIM=1024
├── embedder.py          # Embedder (sentence-transformers wrapper)
├── store.py             # VectorStore (lancedb wrapper)
└── rag.py               # RagService (Embedder+VectorStore 파사드)

tests/vector_search/
# tests/*/__init__.py 생성 금지 (CR-06 일관, specs/M_09 §17 정책)
├── conftest.py          # tmp_db_path, FakeEmbedder, sample_chunks
├── fakes.py             # FakeEmbedder (결정론적 hash→vector)
├── test_types.py        # N-3 format_citation, SearchHit.from_chunk
├── test_embedder.py     # N-7, A-6 (FakeEmbedder 대체) + real_marker S-1
├── test_store.py        # N-1, N-4, N-5, N-6, E-5, E-6, E-7, E-8, A-1 ~ A-4
├── test_rag.py          # N-2, E-1, E-2, E-3, E-4, A-5
└── test_citation.py     # N-3 상세(포맷 4종 경계)
```

패키지명 `vector_search` 채택: 표준 모듈과 충돌 없음. `lancedb`·`sentence-transformers`와 이름 겹침 없음.

---

## 15. 경계 충돌·결정 근거 기록

### 15.1 경계 충돌 A: `RagService.retrieve` 비동기 여부

**충돌 현상**
- `docs/MODULES.md` L252~L253 초안: `async def retrieve(self, query, top_k, category) -> RetrievalResult`.
- `src/tool_router/router.py:229~238`: 실제 호출부가 `run_in_executor(None, lambda: self._rag.retrieve(query, top_k, category))`. **sync** 함수를 가정.

**결정: sync 함수로 확정** (M_09 CalendarService와 동일 정책).

**근거**:
1. **호출자 계약**: ToolRouter의 `_handle_search_docs`가 이미 `run_in_executor`로 감싼 형태로 배포·테스트 완료(M_05b ✅ DONE). 본 모듈을 async로 구현하면 이중 await 또는 event loop 충돌 발생.
2. **I/O 특성이 blocking CPU-bound**:
   - BGE-M3 `encode` → torch forward → GIL release 가능하나 본질적으로 CPU 연산.
   - LanceDB `search` → native Rust 호출, 파일 mmap 읽기. async I/O 경로 없음.
   - 두 경로 모두 async/await의 이점을 얻지 못한다.
3. **M_09 전례**: CalendarService도 동일 이유로 sync 채택(M_09 SPEC §4.3). 일관성 확보.
4. **단순성**: async는 cancellation propagation을 고려해야 하는데, BGE-M3 encode는 사실상 cancel할 수 없다(torch GPU kernel launch 이후는 기다려야 함). sync + executor 패턴이 취소 의미론을 호출자 레벨(executor timeout)로 이동시켜 단순화.

**계약 문서 갱신 플랜**:
- 본 스펙에서 sync로 확정(§4.7).
- **M_07 builder가 구현 완료 후 `docs/MODULES.md` L252~L253의 `async def retrieve` 표기를 `def retrieve`로 정정**하고 근거 각주(본 스펙 §15.1 링크)를 추가. M_09가 동일 패턴으로 처리한 선례(M_09 SPEC §16) 따름.
- 본 스펙 승인만으로 MODULES.md가 자동 갱신되지는 않는다 — builder PR에서 한 커밋으로 묶어 처리.

### 15.2 경계 충돌 B: `SearchHit` 필드 접근 형태

**충돌 현상**
- `docs/MODULES.md` L244~L247 초안: `SearchHit(chunk: DocumentChunk, score: float)` 중첩.
- `src/tool_router/router.py:245~251`: `getattr(hit, "doc_name", None)`, `getattr(hit, "page", None)`, `getattr(hit, "section", None)`, `getattr(hit, "chunk_id", None)`, `getattr(hit, "text", "")` **평면** 접근. getattr의 default가 silent하게 None을 덮어써 버그가 드러나지 않음.

**옵션 비교**

| 옵션 | 장점 | 단점 | 채택 |
|---|---|---|---|
| A. SearchHit 평면 dataclass | ToolRouter 코드와 즉시 정합. JSON 직렬화 1:1. LanceDB row ↔ SearchHit 매핑 자연스러움. | DocumentChunk와 필드 중복(embedding만 차이). | **채택** |
| B. chunk 중첩 + @property 평면 프록시 | 기존 MODULES 초안 유지 + ToolRouter 호환 | 두 가지 접근 공존 혼란. property + frozen dataclass 조합 가독성 낮음. | 기각 |
| C. ToolRouter 수정 요구(별도 CR) | SearchHit 정의 단순 유지 | M_05b가 ✅ DONE인데 재수정은 회귀 리스크. ToolRouter의 평면 접근이 JSON 직렬화에도 유리. | 기각 |

**결정: 옵션 A 채택.**

**근거**:
1. **최소 변경**: M_05b 코드를 건드리지 않는다. ToolRouter ✅ DONE 상태 보존.
2. **silent-mask 제거**: 평면 필드 확정 시 `getattr(..., None)`이 실제로 필드를 반환. 잘못된 dataclass를 넘기면 AttributeError로 조기 실패(테스트로 검증).
3. **LanceDB 매핑 효율**: LanceDB search 결과는 row dict/DataFrame. SearchHit이 평면이면 `**row` unpack에 준하는 단순 매핑. 중첩이면 `DocumentChunk(**row_subset) + score` 2단계 매핑.
4. **MODULES.md L316~L320과의 정합**: M_09의 Event dataclass도 평면이다. 프로젝트 전반의 일관성.

**DocumentChunk와의 관계** (중복 필드를 왜 감수하는가):
- `DocumentChunk`는 **저장 입력**용(doc_id, doc_name, category, page, section, chunk_id, text, bbox, source_path 9필드 + M_06 내부의 embedding 벡터는 별도 `vectors` 인자로 전달).
- `SearchHit`은 **검색 출력**용(위 9필드 복제 + score). embedding 벡터는 포함하지 않음(직렬화·메모리 비용 절감).
- 필드 중복은 **의도된 경계 분리**. DocumentChunk에 score를 추가하는 안(C')는 "저장 계약에 검색 개념 혼입"이므로 기각.

### 15.3 upstream `DocumentChunk` 공유 결정

- M_07이 `src/vector_search/types.py`에 `DocumentChunk` 1곳 정의.
- M_06은 이를 import하여 ingest 경로에서 사용(본 스펙 §4.1.1).
- 대안(M_06에 복제)은 필드 drift 리스크. 기각.

### 15.4 기타 결정

- `merge_insert` 채택(§5.3): `delete+insert` 2단계 대비 단일 호출.
- `brute-force` 검색(§5.2): 1만 스케일에서 IVF_PQ 불필요.
- 점수 정규화 `1 - dist/2`(§6.2.1): LanceDB cosine distance 스펙에 따른 고정 수식.
- 빈 쿼리는 no-match로 분류(§6.3.1): ValueError가 아님. LLM이 빈 쿼리를 유발해도 pipeline이 멈추지 않도록.

---

## 16. 스펙 외 사항 (명시적 제외, 재확인)

본 모듈의 책임이 **아닌** 항목:

1. **문서 파싱·청킹** — M_06 DocumentIngest.
2. **임베딩 모델 다운로드·캐시 관리** — 빌드 타임 `scripts/bundle_deps.sh`.
3. **리랭커·하이브리드·BM25** — ARCHITECTURE D-05.
4. **답변 생성·프롬프트 엔지니어링** — M_05 LLMAgent.
5. **"관련 없음" 한국어 문구의 최종 사용자 제시** — M_05 프롬프트가 `no_match_reason`을 읽어 자연어로 결합. 본 모듈은 reason만 제공.
6. **PDF 뷰어·bbox 하이라이트** — M_12 Frontend.
7. **카테고리 자동 분류·추천** — 사용자 폴더 구조가 진실의 원천(M_06).
8. **min_score 벤치마크·자동 튜닝** — RISKS R-07, 사용자 인스턴스 수동.
9. **멀티 사용자 / 권한 격리** — REQUIREMENTS §10 단일 사용자.
10. **외부 검색·인터넷 조회 (DDG 등)** — REQUIREMENTS §7 범위이며 본 모듈과 무관.

---

## 17. 알려진 한계 (V2 이관)

V1 구현에서 의도적으로 단순화한 항목. 현재 스케일(최대 1만 청크)에서는 허용 범위이나 V2 10만 청크 스케일에서는 개선이 필요하다.

- **VectorStore.upsert 반환값 의미론**: V1에서는 `len(chunks)`(입력 수)만 반환. `merge_insert`의 실제 insert/update 분리 통계를 반영하지 않는다. V2에서 LanceDB `merge_insert(...).execute()`의 반환 dict를 파싱해 정확한 카운트를 반환하도록 확장 가능.
- **delete_by_doc_id 전체 스캔**: V1은 `to_arrow().to_pylist()`로 전체 덤프해 doc_id 매칭. 1만 청크 스케일에서 허용. V2 10만 청크 스케일에서는 §8.2 메모리 예산 위반 위험. LanceDB의 `.delete(f"doc_id = '{...}'")` 기반 서버측 필터 삭제로 전환해 메모리 O(1)화 필요.

---
