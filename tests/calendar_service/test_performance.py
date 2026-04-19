# tests/calendar_service/test_performance.py
"""CalendarService 성능 smoke 테스트.

케이스:
  적대적 (A): A2 — 1만건 seed 후 get_events p95 ≤ 50 ms.

@pytest.mark.slow 마커: 기본 pytest 실행에서는 제외.
  실행: pytest tests/calendar_service/test_performance.py -m slow -v
"""

from __future__ import annotations

import logging
import random
import sqlite3
import time
from datetime import datetime, timedelta, timezone

import pytest

from calendar_service.service import CalendarService

logger = logging.getLogger(__name__)

_SEED_COUNT = 10_000
_QUERY_REPEAT = 50
_P95_THRESHOLD_MS = 50.0


class TestIndexUsage:
    """인덱스 사용 회귀 테스트 — 스펙 §11.2."""

    def test_get_events_uses_start_utc_index(self, db_path: str) -> None:
        """EXPLAIN QUERY PLAN 결과에 idx_events_start_utc 인덱스 사용이 포함되어야 한다.

        스펙 §11.2: "EXPLAIN QUERY PLAN 출력에 USING INDEX idx_events_start_utc 포함을
        회귀 테스트로 확인". 구현 침범 최소화를 위해 별도 sqlite3 커넥션으로 실행.
        """
        # DB 파일을 생성하기 위해 CalendarService를 초기화한 뒤 닫는다.
        svc = CalendarService(db_path)
        svc.close()

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        try:
            rows = conn.execute(
                "EXPLAIN QUERY PLAN "
                "SELECT * FROM events "
                "WHERE start_utc >= ? AND start_utc < ? "
                "ORDER BY start_utc ASC",
                ("2025-01-01T00:00:00+00:00", "2025-12-31T23:59:59+00:00"),
            ).fetchall()
        finally:
            conn.close()

        plan_text = " ".join(str(row["detail"]) for row in rows)
        assert "idx_events_start_utc" in plan_text, (
            f"Expected idx_events_start_utc in EXPLAIN QUERY PLAN output, got: {plan_text!r}"
        )


@pytest.mark.slow
class TestPerformance:
    """A2: 대규모 데이터 성능 smoke 테스트."""

    def test_a2_get_events_p95(self, db_path: str) -> None:
        """A2: 1만건 seed 후 get_events(하루 범위) 50회, p95 ≤ 50 ms.

        pytest log에 실측치를 기록한다.
        """
        svc = CalendarService(db_path)

        try:
            # 1만건 seed: 3년치(2024-2027) 랜덤 분산
            base_date = datetime(2024, 1, 1, tzinfo=timezone.utc)
            three_years_seconds = 3 * 365 * 24 * 3600
            rng = random.Random(42)

            for i in range(_SEED_COUNT):
                offset_sec = rng.randint(0, three_years_seconds)
                start = base_date + timedelta(seconds=offset_sec)
                svc.add_event(f"event_{i}", start, rng.randint(1, 120))

            logger.info("Seeded %d events", _SEED_COUNT)

            # 쿼리 범위: 2025-06-01 하루
            query_start = datetime(2025, 6, 1, 0, 0, tzinfo=timezone.utc)
            query_end = datetime(2025, 6, 2, 0, 0, tzinfo=timezone.utc)

            durations_ms: list[float] = []
            for _ in range(_QUERY_REPEAT):
                t0 = time.perf_counter()
                svc.get_events(query_start, query_end)
                elapsed_ms = (time.perf_counter() - t0) * 1000
                durations_ms.append(elapsed_ms)

            durations_ms.sort()
            p95_idx = int(len(durations_ms) * 0.95)
            p95_ms = durations_ms[p95_idx]
            avg_ms = sum(durations_ms) / len(durations_ms)
            max_ms = durations_ms[-1]

            logger.info(
                "get_events performance: avg=%.2f ms, p95=%.2f ms, max=%.2f ms "
                "(threshold=%.1f ms, queries=%d)",
                avg_ms,
                p95_ms,
                max_ms,
                _P95_THRESHOLD_MS,
                _QUERY_REPEAT,
            )
            print(
                f"\n[A2 Performance] avg={avg_ms:.2f}ms p95={p95_ms:.2f}ms "
                f"max={max_ms:.2f}ms threshold={_P95_THRESHOLD_MS}ms"
            )

            assert p95_ms <= _P95_THRESHOLD_MS, (
                f"p95={p95_ms:.2f} ms exceeds threshold={_P95_THRESHOLD_MS} ms"
            )

        finally:
            svc.close()
