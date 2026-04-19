# tests/e2e/__init__.py
"""E2E 통합 테스트 패키지.

마커:
  e2e        — 전체 E2E (e2e_fast + e2e_model 합집합)
  e2e_fast   — 모델 없이 실행 가능 (CI 대상)
  e2e_model  — 실제 Gemma/Whisper/MeloTTS/BGE-M3 필요 (로컬/스테이지 전용)
"""
