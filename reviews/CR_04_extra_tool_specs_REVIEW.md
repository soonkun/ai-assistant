# CR-04 extra_tool_specs — Critic 검수 결과

## 판정: PASS

## BLOCKER — 없음

- `__init__` / `create` / `build_chat_agent` 세 곳 모두 `extra_tool_specs: list[dict[str, Any]] | None = None` 확인
- 병합 순서 `mcp_tools + extras` (MCP 먼저) 확인 (gemma_chat_agent.py:184)
- 이름 충돌 시 `AgentInitError` FAIL-fast (gemma_chat_agent.py:175-182). WARN+overwrite 없음
- 충돌 검사가 `__init__`에서 수행 → `create()` 정상 전파
- 얕은 복사 `list(extra_tool_specs)` (gemma_chat_agent.py:173)
- 기본값 None 하위호환 — 기존 호출자 무변경
- upstream 변경 없음
- 외부 네트워크 호출 없음
- 스펙 갱신 반영 (M_05_LLMAgent_SPEC.md:16, 229, 245, 255, 390)

## MAJOR — 없음

- N-1, N-2, N-2b, E-1, E-2 모두 구현됨
- 추가 테스트: `test_extras_only_when_use_mcpp_false` (스펙 §5 커버)
- 기존 60개 테스트 회귀 0건

## MINOR (참고)

1. 얕은 복사의 한계 — 내부 dict는 참조 공유. 스펙 범위 내이나 호출자가 내부 dict mutate 가능
2. malformed extras → raw KeyError 전파 가능 (스펙이 검증 요구 안 함)
3. extras 내부 중복 이름 미검사 (스펙 범위 밖, MCP↔extras 충돌만 체크)

## 검증 실행 결과

- ruff format --check: PASS (94 files already formatted)
- ruff check src/agent tests/agent: PASS
- mypy src/agent/: PASS (Success: no issues found in 7 source files)
- pytest tests/agent/ -v: **66 passed** (신규 6 + 기존 60, 회귀 0건)
