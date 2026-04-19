# src/calendar_service/migrations.py
"""SQLite 스키마 마이그레이션 상수.

V1만 존재하는 현재는 상수만 정의.
V2 도입 시 마이그레이션 함수 추가.
"""

from __future__ import annotations

CURRENT_USER_VERSION: int = 1

SCHEMA_V1_DDL: str = """\
CREATE TABLE IF NOT EXISTS events (
  id                INTEGER PRIMARY KEY AUTOINCREMENT,
  title             TEXT NOT NULL,
  start_utc         TEXT NOT NULL,
  duration_minutes  INTEGER NOT NULL,
  description       TEXT,
  created_at_utc    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_start_utc ON events(start_utc);
"""
