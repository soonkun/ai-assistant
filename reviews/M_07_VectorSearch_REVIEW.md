# M_07 VectorSearch — Critic Review

**판정**: APPROVE-WITH-COMMENTS
**일자**: 2026-04-19
**Critic 세션**: fresh, Builder/Validator 컨텍스트 없음
**검토 대상**: `src/vector_search/**`, `tests/vector_search/**`, `specs/M_07_VectorSearch_SPEC.md`, `pyproject.toml`, `scripts/bundle_deps.sh`, `docs/MODULES.md`

---

## 점검 결과 요약

| 카테고리 | 결과 |
|---|---|
| A. 공개 API 계약 (sync / 평면 SearchHit / 시그니처) | **통과** — 스펙 §4·§15와 100% 정합. 10필드 평면 dataclass, `retrieve`는 sync. |
| B. LanceDB 스키마 (§5) | **통과** — FixedSizeListType 검증 OK, `vector_column_name="vector"` 명시됨(`bbox` 혼동 차단). |
| C. 알고리즘 (§6.1·§6.2·§6.3) | **통과** — 점수 수식 `1 - d/2`, 빈 쿼리 정책, top_k clamp 모두 정합. |
| D. 오프라인 / §0 준수 | **통과** — 네트워크 호출 0건, `HF_HUB_OFFLINE/TRANSFORMERS_OFFLINE` 설정, `local_files_only=True`. |
| E. 에러 정책 (§8·§9) | **통과** — `EmbedderError`/`VectorStoreError`/`ValueError` 분리 OK. |
| F. 테스트 커버 (§11) | **통과** — 정상 ≥5, 엣지 ≥5, 적대적 ≥3 모두 충족. 68 passed / 1 skipped(@slow). |
| G. 의존성·번들 | **통과** — pyproject 핀 범위 정합, bundle_deps.sh에 BGE-M3 다운로드 포함. |
| H. 문서 동기화 | **부분 위반** — MODULES.md 본문은 갱신됐으나 **요약 테이블 L423이 `🔲 TODO` 그대로**. (MED-4) |

검수 결과 **HIGH 심각도 위반은 없음**. MED 4건, LOW 3건. 판정은 APPROVE-WITH-COMMENTS.

---

## HIGH 이슈 (REJECT 사유)

없음. 주요 계약(sync retrieve, 평면 SearchHit, 10필드, 점수 수식, 오프라인, LanceDB 스키마, 예외 분리, top_k ValueError, E-3 hits 유지, SQL-like 방어)은 모두 스펙과 일치한다.

참고 검증 증적:
- `inspect.iscoroutinefunction(RagService.retrieve) == False` (src/vector_search/rag.py:39) — §15.1 준수.
- `dataclasses.fields(SearchHit)` → `['doc_id', 'doc_name', 'category', 'page', 'section', 'chunk_id', 'text', 'bbox', 'source_path', 'score']` (types.py:33~60) — §4.2 10필드 평면 OK.
- 점수 정규화 `score = max(0.0, min(1.0, 1.0 - distance / 2.0))` (store.py:50) — §6.2.1과 문자 그대로 일치.
- `os.environ.setdefault("HF_HUB_OFFLINE", "1")` + `local_files_only=True` (embedder.py:45~64) — §4.5.1 준수.
- `vector_column_name="vector"` 명시 (store.py:244) — `bbox`(list<float32,4>)와 혼동 방지.
- `pa.list_(pa.float32(), 1024)` → 실측 `FixedSizeListType.list_size == 1024` 확인.
- 네트워크 호출 grep 0건: `rg 'http|https|snapshot_download|HfApi|urllib|urlopen|requests\.|fetch' src/vector_search/` → no matches.
- 실제 SQL-like 인젝션 smoke: `category="' OR 1=1 --"` 주입 시 LanceDB가 escaped WHERE로 0건 반환, 다른 카테고리 유출 없음. 정상 quote 포함 카테고리(`"cat with ' quote"`)는 여전히 round-trip 성공.
- `pytest tests/vector_search/ -v`: **68 passed, 1 skipped (@slow)**, `ruff check`, `mypy src/vector_search/` 모두 통과.

---

## MEDIUM 이슈

### [MED-1] `VectorStore.upsert` 반환값이 스펙의 "merge_insert 통계 활용"과 다름

- **파일:라인**: `src/vector_search/store.py:212` — `return len(chunks)`
- **스펙**: §4.6 "Returns: 실제 written row 수(신규 insert + 업데이트 합). **LanceDB의 merge_insert 통계 활용**."
- **현재 구현**: merge_insert 반환값을 무시하고 입력 chunks 수를 그대로 반환.
- **위험**: 일부 row가 스키마 검증에서 묵시적으로 drop되거나 부분 실패해도 호출자는 알 수 없다. A-1 테스트(중복 chunk_id → row 1개)는 "실제 written = 1"이 맞지만 impl은 `2`를 반환(2번째 upsert에서 `len(chunks)=1`이므로 A-1 자체는 우연히 맞지만, 멱등 의미상 스펙의 "written count" 계약은 깨진다).
- **권고 조치**: LanceDB `merge_insert(...).execute(...)` 반환 dict의 `num_inserted_rows`·`num_updated_rows`를 합산해 반환하거나, 스펙 §4.6의 "통계 활용" 문구 자체를 "입력 길이"로 CR 처리. 현 시점 실용상 기능은 동작하므로 MEDIUM.

### [MED-2] `VectorStore.delete_by_doc_id`가 전체 테이블을 메모리에 적재

- **파일:라인**: `src/vector_search/store.py:276~278` — `arrow_tbl: pa.Table = self._tbl.to_arrow(); doc_ids = arrow_tbl.column("doc_id").to_pylist()`
- **스펙 §9 테이블**: `delete_by_doc_id doc_id 미존재 → 0 반환`, **"Returns: 삭제된 row 수"** (§4.6).
- **문제**: before_count 계산을 위해 **매 호출마다 전체 테이블을 arrow로 덤프 + to_pylist**. 1만 청크(§8.1 성능표 스케일)에서 수십 MB 피크 메모리 + O(N) 파이썬 리스트 순회. §8.2 "PyArrow/Pandas 중간 버퍼 ≤ 100 MB 피크" 가정에 근접. 10만 청크 V2(§5.2)에선 명백히 위반.
- **대안**: LanceDB `table.count_rows(filter=...)` 또는 `table.search().where(...).limit(N_max)` 등 조건부 카운트 API 사용. 또는 카운트 포기하고 `delete(filter)` 이전/이후 `count_rows()`만 차이 계산.
- **권고 조치**: `count_rows(f"doc_id = '{escaped}'")` 확인 후 fallback 경로로 축소. 현재 스케일에선 동작하므로 MEDIUM.

### [MED-3] E-3 테스트가 스펙 §11.3 E-3의 "구체적 숫자 검증"을 약화

- **파일:라인**: `tests/vector_search/test_rag.py:129~147` (`test_e3_no_match_reason_contains_scores`)
- **스펙 §11.3 E-3**: `no_match_reason 문자열에 "0.34"와 "0.35" 포함. len(hits) == top_k`.
- **현재 구현**:
  - `min_score=0.9999` 사용 → `.2f` 포맷하면 `"1.00"`이 출력된다 (0.35가 아님). 테스트는 `re.search(r"\d+\.\d+", ...)`로 임의의 소수만 확인하여 **"0.35" 문자열 존재 여부를 검증하지 않는다**.
  - `top_score`를 0.34 근방으로 조정하지 않고, FakeEmbedder 난수 결과에 맡긴다.
  - `len(hits) == top_k` 등식 검증 없음 (`> 0`만 확인).
- **위험**: `.2f` 포맷 버그(예: `{top_score}` 없이 `{min_score}`만 출력) 같은 실수를 잡지 못한다.
- **권고 조치**: FakeEmbedder로 `top_score≈0.34`를 유도할 수 있도록 vector를 고정 sketch → `min_score=0.35` 설정. `assert "0.35" in reason and "0.34" in reason`을 추가. `assert len(result.hits) == top_k`도 추가.

### [MED-4] `docs/MODULES.md` 상태 테이블 미갱신

- **파일:라인**: `docs/MODULES.md:423` — `| M_07 | VectorSearch | NEW | 🔲 TODO | — |`
- **스펙 §12.5 / §14.5**: "Critic PASS 후 상태 `✅ DONE`으로 갱신" + 본문은 `🚧 WIP`로 갱신됨(L225). 하지만 **요약 테이블이 여전히 `🔲 TODO`**. 두 표기가 충돌한다.
- **권고 조치**: Critic PASS 기록 직후 테이블 L423을 `🚧 WIP` 또는 `✅ DONE`(통합 단계에 따라)으로 일치시키고 `의존` 컬럼을 스펙 언급대로 `sentence-transformers, lancedb, pyarrow` 등으로 보정. 현재는 본문과 테이블 간 명시적 모순.

---

## LOW / 권고

### [LOW-1] CPU fallback 경로에서 `model_name_or_path` 의존
- `src/vector_search/embedder.py:128`. SentenceTransformer의 공개 속성은 아니며 내부 구현 변경에 취약. 현재 v3.x에서는 `__init__`이 self에 저장하지만, 향후 패치로 private으로 바뀌면 `AttributeError`를 삼켜 **테스트 없이 사일런트 실패**할 수 있다. `self._model_path: str`을 `__init__`에서 캐시해두고 재사용하는 것이 안전.

### [LOW-2] `top_k_max` clamp가 경고 없이 조용히 정답을 왜곡
- `rag.py:78~80` — `warning` 로그만 출력. 사용자가 `top_k=1000`을 명시적으로 원해 Debug 시 잡아내기 어렵다. 스펙이 "warning 로그"만 요구하므로 위반은 아니지만, `RetrievalResult`에 `clamped_top_k: int | None` 같은 디버그 필드를 추가하면 좋다(스펙 변경 필요).

### [LOW-3] `store.py:180~184` Arrow 테이블 빌드에서 `category`/`page`/`section` 컬럼만 명시 타입 지정
- `doc_id`, `doc_name`, `chunk_id`, `text`, `source_path`는 타입 추론에 의존. 이론상 None 포함 시(예: 누군가 DocumentChunk에서 doc_id=None을 넣었을 때)는 자동 타입이 예상과 다를 수 있다. DocumentChunk 계약은 non-null이라 현재는 문제 없지만 `pa.array([...], type=pa.string())` 을 전 컬럼 적용하는 편이 방어적.

### [LOW-4] `VectorStoreError` 하위 체인 원인 보존
- `store.py:100`, `:209`, `:257` 모두 `raise VectorStoreError(...) from exc`로 체인을 보존. 적절. 단 `_open_or_create_table`의 `KeyError` 경로(line 135)는 `from exc` 누락. 마이너하지만 trace 연결을 위해 `raise VectorStoreError(...) from e`로 바꿀 것.

---

## 스펙 vs 구현 매핑 검증 (발췌)

| 스펙 항목 | 구현 위치 | 상태 |
|---|---|---|
| `DocumentChunk` 9필드 1곳 정의 | `types.py:10~29` | 통과 |
| `SearchHit` 평면 10필드 | `types.py:33~60` | 통과 |
| `SearchHit.from_chunk` 헬퍼 | `types.py:62~76` | 통과 |
| `RetrievalResult` 3필드 | `types.py:80~86` | 통과 |
| 예외 4종 | `errors.py:5~19` | 통과 |
| `CHUNKS_SCHEMA` 10필드 | `schema.py:8~21` | 통과 |
| `Embedder(model_dir, device, batch_size, normalize)` | `embedder.py:37~43` | 통과 |
| `embed_passages → (N,1024) float32` | `embedder.py:100~145` | 통과 |
| `embed_query → (1024,)` | `embedder.py:159~167` | 통과 |
| NaN/Inf 감지 → `EmbedderError` | `embedder.py:141~142` | 통과 |
| CUDA unavailable + device="cuda" → `EmbedderError` | `embedder.py:75~85` | 통과 |
| `VectorStore.__init__(db_path, table)` | `store.py:94` | 통과 |
| 기존 테이블 dim 1024 검증 | `store.py:115~134` | 통과 |
| `upsert` 차원/길이 검증 | `store.py:161~169` | 통과 |
| `merge_insert("chunk_id")` | `store.py:202~207` | 통과 |
| `search` query_vec shape 검증 | `store.py:229~232` | 통과 |
| `search top_k<=0 → ValueError` | `store.py:234~236` | 통과 |
| `search top_k>50 → clamp` | `store.py:238~240` | 통과 |
| `_escape_category` + 제어문자 거부 | `store.py:19~27` | 통과 |
| 점수 정규화 `1 - d/2` | `store.py:49~50` | 통과 |
| `delete_by_doc_id` 0 반환 정책 | `store.py:280~282` | 통과 (MED-2 참조) |
| `RagService(embedder, store, min_score=0.35, top_k_max=20)` | `rag.py:26~37` | 통과 |
| `retrieve`는 sync | `rag.py:39` | 통과 |
| 빈 쿼리 → no-match + Embedder 미호출 | `rag.py:63~70` | 통과 |
| `top_k<=0 → ValueError` | `rag.py:73~75` | 통과 |
| `top_k > top_k_max → clamp` | `rag.py:78~80` | 통과 |
| `found=False && hits 유지` | `rag.py:92~101` | 통과 |
| `format_citation` 4조합 | `rag.py:106~125` | 통과 |
| ToolRouter 평면 접근 (`hit.doc_name` 등) 호환 | 통합 smoke로 확인 | 통과 |

## 테스트 커버 검증

| 스펙 테스트 ID | 구현 매핑 | 상태 |
|---|---|---|
| N-1 upsert→search round-trip | `test_store.py::test_n1_upsert_search_roundtrip` | 통과 |
| N-2 retrieve found=True | `test_rag.py::test_n2_retrieve_found_true` | 통과 |
| N-3 format_citation 4조합 | `test_citation.py::TestFormatCitation::*` | 통과 |
| N-4 delete_by_doc_id 멱등 | `test_store.py::test_n4_delete_by_doc_id_idempotent` | 통과 |
| N-5 category 필터 | `test_store.py::test_n5_category_filter` | 통과 |
| N-6 점수 정규화 | `test_store.py::test_n6_score_normalization` | 부분 통과 — score≈0.5(distance=1.0) 케이스 없음 |
| N-7 embed_passages 빈 리스트 | `test_embedder.py::test_embed_passages_empty_list` | 통과 |
| E-1 빈 쿼리 | `test_rag.py::test_e1_empty_query` + `test_e1_no_embedder_called_on_empty` | 통과 |
| E-2 공백만 쿼리 | `test_rag.py::test_e2_whitespace_only_query` | 통과 |
| E-3 min_score 경계 + 수치 포함 | `test_rag.py::test_e3_score_below_min_score_found_false_hits_preserved`, `test_e3_no_match_reason_contains_scores` | MED-3 — 수치 검증 약화 |
| E-4 top_k=1 | `test_rag.py::test_e4_top_k_1` | 통과 |
| E-5 top_k 상한 clamp | `test_rag.py::test_e5_top_k_clamp` + `test_store.py::test_e5_top_k_clamp_at_max` | 통과 |
| E-6 upsert 빈 | `test_store.py::test_e6_upsert_empty_chunks` | 통과 |
| E-7 category 한글·특수문자 | `test_store.py::test_e7_category_with_special_chars` | 통과 |
| E-8 bbox round-trip | `test_store.py::test_e8_bbox_roundtrip` | 통과 |
| A-1 중복 chunk_id 멱등 | `test_store.py::test_a1_duplicate_chunk_id_upsert` | 통과 |
| A-2 upsert 차원/길이 불일치 | `test_store.py::test_a2_upsert_wrong_dim`, `test_a2_upsert_mismatched_count` | 통과 |
| A-3 category SQL-like 주입 | `test_store.py::test_a3_sql_injection_category` | 통과 |
| A-4 query_vec shape 공격 | `test_store.py::test_a4_query_vec_wrong_shape_2d`, `test_a4_query_vec_wrong_dim` | 통과 |
| A-5 매우 긴 쿼리 | `test_rag.py::test_a5_very_long_query` | 통과 |
| A-6 NaN/Inf 방어 | `test_embedder.py::test_nan_in_embedder_raises_embedder_error`, `test_inf_in_embedder_raises_embedder_error`, `test_rag.py::test_a6_nan_from_embedder_propagates` | 통과 |
| S-1 실모델 smoke (@slow) | `test_embedder.py::test_real_embedder_load_and_embed` | skip OK (--run-slow 옵션) |

---

## Out-of-Scope 위반 여부 (§1.3)

검토 결과 **위반 없음**. 리랭커, 하이브리드(BM25) 검색, 자동 카테고리 분류, Qdrant/ChromaDB, 문서 파싱, LLM 호출, PDF 뷰어, 모델 다운로드 등 금지 피처의 흔적 없음. `subprocess`/`docker` 호출 없음.

## 의존성·번들 검증

- `pyproject.toml:36~39` — `sentence-transformers>=3.0,<5`, `lancedb>=0.10,<1`, `pyarrow>=15.0,<19`, `numpy>=1.26,<3` 모두 스펙 §13.1 범위와 일치.
- mypy overrides로 stub 부재 대응(`sentence_transformers`, `lancedb`, `pyarrow`) 설정됨(pyproject.toml:112~120).
- `scripts/bundle_deps.sh:106~124` — M_07 섹션에 4개 패키지 `pip download` + `huggingface-cli download BAAI/bge-m3` 포함. 빌드 타임 사전 배치 의무(CLAUDE.md) 충족.

---

## 검토하지 못한 영역 / 다음 Critic에 남김

1. **성능 예산(§8.1) 실측**: `Embedder.embed_query p95 ≤ 300ms`, `retrieve end-to-end p95 ≤ 700ms`, `VectorStore.search(1만 청크) p95 ≤ 50ms` 모두 실측 로깅 없음. DoD §12.2에 기재됐으나 @slow bench도 없다. 통합 단계(M_07 DoD §12.3)에서 ToolRouter 통합 테스트로 검증 권고.
2. **다른 모듈과의 통합 regression**: `tests/tool_router/test_dispatch_normal.py`가 실제 `RagService` + 실 LanceDB를 사용하는 경로(DoD §12.3 마지막 항목)로 회귀 테스트되는지 본 리뷰 범위 밖. integrator 단계에서 재확인 필요.
3. **fp16→fp32 승격(§4.5.2 마지막 문장)**: "fp16 저장 가중치라도 device=cpu면 자동 fp32 승격" — 실모델 로드 @slow에서만 검증 가능. 본 리뷰에서는 smoke 미실행.
4. **LanceDB 0.30.x 대비 호환**: `store.py:110~111`의 `list_tables()` return value 분기는 두 버전 대응 추정 코드. 실제 설치된 lancedb 버전으로만 동작 확인됨(실측 환경 OK), 다른 버전에서 회귀 가능성.

---

## 요약

- 스펙 계약 핵심(sync retrieve / 평면 SearchHit 10필드 / 점수 수식 / 오프라인 env / 예외 분리 / SQL-like 방어 / 테스트 수량) **모두 준수**.
- 실제 pytest 68 passed / 1 skipped, ruff·mypy 클린.
- **HIGH 이슈 0건, MEDIUM 4건, LOW 4건**. MED-3(E-3 수치 검증 약화), MED-4(MODULES.md 테이블 미갱신)는 머지 전 반드시 수정 권고. MED-1(upsert 반환값 스펙 이탈), MED-2(delete_by_doc_id O(N) 스캔)는 기능 영향 없으나 기록 필요.
- **판정: APPROVE-WITH-COMMENTS**. 위 MED 4건을 같은 PR 혹은 후속 patch commit으로 수정한 뒤 M_07 상태를 `✅ DONE`으로 승격할 것.
