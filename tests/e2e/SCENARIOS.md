# E2E 시나리오 목록

본 파일은 `docs/E2E_SCENARIOS.md`에서 파생된 구현 레퍼런스다.
원본 설계 계약은 `docs/E2E_SCENARIOS.md`를 단일 진실 공급원으로 한다.

## 시나리오-파일 매핑

| 시나리오 ID | 파일 | 마커 | 상태 |
|---|---|---|---|
| E2E-01 | test_e2e_01_chat_happy.py | e2e_fast (FakeAgent) / e2e_model (실제 Gemma) | 구현됨 |
| E2E-02 | test_e2e_02_voice_happy.py | e2e_model | 구현됨 |
| E2E-03 | test_e2e_03_tool_call_calendar.py | e2e_model | 구현됨 |
| E2E-04 | test_e2e_04_tool_call_search.py | e2e_model | 구현됨 |
| E2E-05 | test_e2e_05_proactive_morning_briefing.py | e2e_fast | 구현됨 |
| E2E-06 | test_e2e_06_proactive_idle_rest.py | e2e_fast | 구현됨 |
| E2E-07 | test_e2e_07_avatar_emotion_roundtrip.py | e2e_fast (FakeAgent) | 구현됨 |
| E2E-08 | test_e2e_08_citation_links.py | e2e_model | 구현됨 |
| E2E-09 | test_e2e_09_event_reminder_interval.py | e2e_fast | 구현됨 |
| E2E-20 | test_e2e_20_ollama_down.py | e2e_fast | 구현됨 |
| E2E-21 | test_e2e_21_empty_asr.py | e2e_model | 구현됨 |
| E2E-22 | test_e2e_22_no_match_rag.py | e2e_fast (FakeAgent) | 구현됨 |
| E2E-23 | test_e2e_23_calendar_duplicate.py | e2e_model | 구현됨 |
| E2E-24 | test_e2e_24_dnd_drop.py | e2e_fast | 구현됨 |
| E2E-25 | test_e2e_25_ws_reconnect.py | e2e_fast | 구현됨 |
| E2E-26 | test_e2e_26_session_not_ready_screenshot.py | e2e_fast | 구현됨 |
| E2E-27 | test_e2e_27_tts_init_fail_text_only.py | e2e_fast | 구현됨 |
| E2E-30 | test_e2e_30_tool_schema_violation.py | e2e_fast | 구현됨 |
| E2E-31 | test_e2e_31_unknown_emotion_tag.py | e2e_fast | 구현됨 |
| E2E-32 | test_e2e_32_network_offline_guard.py | e2e_fast | 구현됨 |
| E2E-33 | test_e2e_33_interrupt_midspeech.py | e2e_fast (FakeAgent) | 구현됨 |
| static | test_static_guard.py | e2e_fast | 구현됨 |
