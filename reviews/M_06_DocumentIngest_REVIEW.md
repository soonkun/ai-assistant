# M_06 DocumentIngest — Critic 리뷰 기록

## R1: FAIL (2026-04-23)

### MAJOR
- **M-1**: `doc_id = SHA-256(path + ":" + mtime_ns)` 로 mtime 변경 시 doc_id가 달라져 재-ingest 때마다 구 청크가 삭제되지 않고 누적됨. 스펙 §7.1 / §11.2 N-8 / DoD §12.2 위반.
- **M-2**: `ingest_directory`의 `except Exception`이 `EmbedderError`·`VectorStoreError` 등 치명적 예외를 침묵 skip. 스펙 §9 "embedder/store 예외 → 상위로 전파" 위반.

---

## R2: PASS (2026-04-23)

### MAJOR 해소 확인
- **M-1 해소**: `_make_doc_id`를 `SHA-256(str(abs_path))[:32]` (path-only)로 수정. 테스트 N-8이 `count2 == count1` + LanceDB row 수 직접 검증으로 강화됨.
- **M-2 해소**: `except (ParseError, UnsupportedFormatError)`로 화이트리스트 좁힘. `IngestIOError` 명시 re-raise. 그 외 예외 자동 전파.

### MINOR (FAIL 사유 아님)
- m-1: 스펙 §4/§6.4 doc_id 정의가 path-only 코드와 불일치 → 스펙 본문 동기화 필요 (별도 처리)
- m-2: defusedxml.defuse_stdlib()은 lxml 미패치, python-docx의 resolve_entities=False에 의존
- m-3: `_make_doc_id` 중복 stat() 호출 (무해)
- m-4: `overlap_chars < 0` 생성자 미검증
- m-5/m-6: 일부 적대적 테스트의 assertion이 약함 (count >= 0)

### 결론
PASS. 재-ingest 멱등성·예외 전파 정책 모두 해소. MINOR 5건은 릴리즈 차단 아님.
