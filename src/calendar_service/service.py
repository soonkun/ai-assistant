# src/calendar_service/service.py
"""CalendarService — SQLite 기반 일정 CRUD 서비스.

본 모듈은 순수 데이터 계층이다. 자연어 날짜 파싱·알림 송신·브리핑 문장 생성은
담당하지 않는다. 호출자(M_05b / M_11)는 ISO 8601 문자열로 datetime 변환을 완료한 후
본 모듈에 전달한다.
"""

from __future__ import annotations

import logging
import os
import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from .errors import (
    CalendarDBError,
    CalendarInitError,
    CalendarValidationError,
    EventNotFoundError,
)
from .migrations import CURRENT_USER_VERSION, SCHEMA_V1_DDL

logger = logging.getLogger(__name__)

_KST: ZoneInfo = ZoneInfo("Asia/Seoul")

# 검증 상수
_TITLE_MAX: int = 500
_DURATION_MIN: int = 1
_DURATION_MAX: int = 1440
_DESC_MAX: int = 4000


@dataclass(frozen=True)
class Event:
    """단일 일정 레코드.

    - ``start`` / ``created_at`` 은 **반드시 tz-aware** (tzinfo != None).
    - 내부 저장은 UTC ISO 8601, 반환 시 ``CalendarService.default_tz`` 기준으로
      astimezone 후 전달한다.
    - frozen=True: 호출자 수정 방지. 수정은 반드시 ``update_event`` 경유.
    """

    id: int
    title: str
    start: datetime  # tz-aware
    duration_minutes: int
    description: str | None
    created_at: datetime  # tz-aware


def _now_utc() -> datetime:
    """현재 UTC 시각 반환. 테스트에서 monkeypatch 교체 가능."""
    return datetime.now(timezone.utc)


def _to_utc(dt: datetime, default_tz: ZoneInfo) -> datetime:
    """datetime을 UTC로 변환한다.

    tz-naive이면 ``default_tz`` 로 가정한 뒤 UTC로 변환하고 경고를 기록한다.
    """
    if dt.tzinfo is None:
        logger.warning(
            "naive datetime received; assumed default_tz=%s",
            default_tz,
        )
        dt = dt.replace(tzinfo=default_tz)
    return dt.astimezone(timezone.utc)


def _row_to_event(row: sqlite3.Row, default_tz: ZoneInfo) -> Event:
    """sqlite3.Row → Event 변환."""
    start_utc = datetime.fromisoformat(row["start_utc"])
    created_utc = datetime.fromisoformat(row["created_at_utc"])
    return Event(
        id=row["id"],
        title=row["title"],
        start=start_utc.astimezone(default_tz),
        duration_minutes=row["duration_minutes"],
        description=row["description"],
        created_at=created_utc.astimezone(default_tz),
    )


def _validate_title(title: Any) -> str:
    """title 검증. 실패 시 CalendarValidationError."""
    if not isinstance(title, str):
        raise CalendarValidationError(f"title must be a str, got {type(title).__name__!r}")
    stripped = title.strip()
    if not stripped or len(stripped) > _TITLE_MAX:
        raise CalendarValidationError(
            f"title must be 1~{_TITLE_MAX} chars after strip, got {len(stripped)!r}"
        )
    return title  # 원본(공백 포함) 저장, strip은 검증에만 사용


def _validate_duration(duration_minutes: Any) -> int:
    """duration_minutes 검증. 실패 시 CalendarValidationError."""
    if not isinstance(duration_minutes, int) or isinstance(duration_minutes, bool):
        raise CalendarValidationError(
            f"duration_minutes must be int, got {type(duration_minutes).__name__!r}"
        )
    if not (_DURATION_MIN <= duration_minutes <= _DURATION_MAX):
        raise CalendarValidationError(
            f"duration_minutes must be {_DURATION_MIN}~{_DURATION_MAX}, got {duration_minutes!r}"
        )
    return duration_minutes


def _validate_description(description: Any) -> str | None:
    """description 검증. 실패 시 CalendarValidationError.

    빈 문자열("") → None으로 정규화(스펙 §7).
    """
    if description is None:
        return None
    if not isinstance(description, str):
        raise CalendarValidationError(
            f"description must be str or None, got {type(description).__name__!r}"
        )
    if len(description) > _DESC_MAX:
        raise CalendarValidationError(
            f"description must be 0~{_DESC_MAX} chars, got {len(description)!r}"
        )
    return description if description else None


def _validate_start(start: Any) -> datetime:
    """start가 datetime 인스턴스인지 검증."""
    if not isinstance(start, datetime):
        raise CalendarValidationError(f"start must be datetime, got {type(start).__name__!r}")
    return start


class CalendarService:
    """SQLite 기반 일정 CRUD 서비스.

    모든 공개 메서드는 동기(sync)이며 ``threading.RLock`` 으로 보호된다.
    """

    def __init__(
        self,
        db_path: str,
        *,
        default_tz: ZoneInfo = _KST,
    ) -> None:
        """CalendarService 초기화.

        Args:
            db_path: SQLite DB 파일 경로. 디렉토리가 없으면 자동 생성.
            default_tz: tz-naive datetime을 받았을 때 가정할 타임존.
                기본값은 Asia/Seoul(KST).

        Raises:
            CalendarInitError: DB 생성·스키마 초기화 실패 또는 DB 버전이 지원 범위 초과.
        """
        self.default_tz: ZoneInfo = default_tz
        self._lock: threading.RLock = threading.RLock()
        self._conn: sqlite3.Connection | None = None

        # 디렉토리 자동 생성
        dir_path = os.path.dirname(os.path.abspath(db_path))
        try:
            os.makedirs(dir_path, exist_ok=True)
        except OSError as exc:
            raise CalendarInitError(f"Failed to create DB directory {dir_path!r}: {exc}") from exc

        # DB 연결
        try:
            conn = sqlite3.connect(
                db_path,
                check_same_thread=False,
                isolation_level=None,  # autocommit
            )
        except sqlite3.Error as exc:
            raise CalendarInitError(f"Failed to connect to SQLite DB {db_path!r}: {exc}") from exc

        conn.row_factory = sqlite3.Row

        # WAL 모드 + synchronous NORMAL
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA synchronous = NORMAL")
        except sqlite3.Error as exc:
            conn.close()
            raise CalendarInitError(f"Failed to set PRAGMA: {exc}") from exc

        # user_version 확인 및 스키마 초기화
        try:
            user_version: int = conn.execute("PRAGMA user_version").fetchone()[0]
            if user_version == 0:
                # 신규 DB — DDL 실행 후 버전 기록
                conn.executescript(SCHEMA_V1_DDL)
                conn.execute(f"PRAGMA user_version = {CURRENT_USER_VERSION}")
                logger.info(
                    "CalendarService: DB schema V%d created at %r",
                    CURRENT_USER_VERSION,
                    db_path,
                )
            elif user_version > CURRENT_USER_VERSION:
                conn.close()
                raise CalendarInitError(
                    f"DB schema newer than supported: "
                    f"found V{user_version}, supports up to V{CURRENT_USER_VERSION}"
                )
            else:
                logger.info(
                    "CalendarService: existing DB schema V%d at %r",
                    user_version,
                    db_path,
                )
        except CalendarInitError:
            raise
        except sqlite3.Error as exc:
            conn.close()
            raise CalendarInitError(f"Schema initialization failed: {exc}") from exc

        self._conn = conn
        logger.info("CalendarService: initialized with db_path=%r", db_path)

    def _require_open(self) -> sqlite3.Connection:
        """연결이 열려있음을 보장. 닫혀있으면 CalendarDBError."""
        if self._conn is None:
            raise CalendarDBError("calendar service is closed")
        return self._conn

    def add_event(
        self,
        title: str,
        start: datetime,
        duration_minutes: int,
        description: str | None = None,
    ) -> Event:
        """일정을 추가하고 생성된 Event를 반환한다.

        Args:
            title: 일정 제목 (1~500자, strip 후).
            start: 시작 시각 (tz-aware 권장; tz-naive면 default_tz 가정 + 경고).
            duration_minutes: 소요 시간 분 (1~1440).
            description: 설명 (None 또는 0~4000자). 빈 문자열은 None으로 저장.

        Returns:
            생성된 Event (id 포함, start/created_at은 default_tz 기준).

        Raises:
            CalendarValidationError: 입력 검증 실패.
            CalendarDBError: SQLite 오류.
        """
        # 검증
        title = _validate_title(title)
        start = _validate_start(start)
        duration_minutes = _validate_duration(duration_minutes)
        description = _validate_description(description)

        with self._lock:
            conn = self._require_open()

            start_utc = _to_utc(start, self.default_tz)
            now_utc = _now_utc()
            start_utc_str = start_utc.isoformat()
            now_utc_str = now_utc.isoformat()

            # 중복 체크 (title, start_utc) — 허용하되 경고 기록
            try:
                existing = conn.execute(
                    "SELECT COUNT(*) FROM events WHERE title = ? AND start_utc = ?",
                    (title, start_utc_str),
                ).fetchone()[0]
            except sqlite3.Error as exc:
                raise CalendarDBError(f"Duplicate check failed: {exc}") from exc

            if existing > 0:
                logger.warning(
                    "duplicate event: title=%r start=%s; creating new id",
                    title,
                    start_utc_str,
                )

            try:
                cursor = conn.execute(
                    "INSERT INTO events (title, start_utc, duration_minutes, description, created_at_utc) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (title, start_utc_str, duration_minutes, description, now_utc_str),
                )
                event_id = cursor.lastrowid
            except sqlite3.Error as exc:
                raise CalendarDBError(f"INSERT failed: {exc}") from exc

            logger.info(
                "CalendarService.add_event: id=%d title=%r start=%s",
                event_id,
                title,
                start_utc_str,
            )

            event = Event(
                id=event_id,  # type: ignore[arg-type]
                title=title,
                start=start_utc.astimezone(self.default_tz),
                duration_minutes=duration_minutes,
                description=description,
                created_at=now_utc.astimezone(self.default_tz),
            )
            return event

    def get_events(
        self,
        start: datetime,
        end: datetime,
    ) -> list[Event]:
        """반열린 구간 ``[start, end)`` 에 속하는 이벤트를 start ASC로 반환한다.

        ``start > end`` 이면 빈 리스트를 반환한다(예외 아님, 스펙 §10).

        Args:
            start: 구간 시작 (포함).
            end: 구간 끝 (미포함).

        Returns:
            Event 리스트 (start ASC 정렬).

        Raises:
            CalendarDBError: SQLite 오류.
        """
        start = _validate_start(start)
        end = _validate_start(end)

        with self._lock:
            conn = self._require_open()

            start_utc = _to_utc(start, self.default_tz)
            end_utc = _to_utc(end, self.default_tz)

            # start >= end인 경우 빈 리스트
            if start_utc >= end_utc:
                return []

            try:
                rows = conn.execute(
                    "SELECT id, title, start_utc, duration_minutes, description, created_at_utc "
                    "FROM events "
                    "WHERE start_utc >= ? AND start_utc < ? "
                    "ORDER BY start_utc ASC",
                    (start_utc.isoformat(), end_utc.isoformat()),
                ).fetchall()
            except sqlite3.Error as exc:
                raise CalendarDBError(f"SELECT (get_events) failed: {exc}") from exc

            return [_row_to_event(row, self.default_tz) for row in rows]

    def get_event(self, event_id: int) -> Event | None:
        """단일 이벤트 조회. 존재하지 않으면 None 반환.

        Args:
            event_id: 조회할 이벤트 id.

        Returns:
            Event 또는 None.

        Raises:
            CalendarDBError: SQLite 오류.
        """
        with self._lock:
            conn = self._require_open()
            try:
                row = conn.execute(
                    "SELECT id, title, start_utc, duration_minutes, description, created_at_utc "
                    "FROM events WHERE id = ?",
                    (event_id,),
                ).fetchone()
            except sqlite3.Error as exc:
                raise CalendarDBError(f"SELECT (get_event) failed: {exc}") from exc

            if row is None:
                return None
            return _row_to_event(row, self.default_tz)

    def update_event(self, event_id: int, **fields: Any) -> Event:
        """이벤트 필드를 수정하고 갱신된 Event를 반환한다.

        지원 필드: ``title``, ``start``, ``duration_minutes``, ``description``.
        전달하지 않은 필드는 기존 값을 유지한다.

        Args:
            event_id: 수정할 이벤트 id.
            **fields: 수정할 필드 (title, start, duration_minutes, description).

        Returns:
            갱신된 Event.

        Raises:
            EventNotFoundError: event_id가 존재하지 않음.
            CalendarValidationError: 입력 검증 실패.
            CalendarDBError: SQLite 오류.
        """
        with self._lock:
            conn = self._require_open()

            # 존재 여부 확인
            existing = self.get_event(event_id)
            if existing is None:
                raise EventNotFoundError(f"Event id={event_id} not found")

            # 수정할 컬럼 구성
            set_clauses: list[str] = []
            params: list[Any] = []

            if "title" in fields:
                title = _validate_title(fields["title"])
                set_clauses.append("title = ?")
                params.append(title)

            if "start" in fields:
                start = _validate_start(fields["start"])
                start_utc = _to_utc(start, self.default_tz)
                set_clauses.append("start_utc = ?")
                params.append(start_utc.isoformat())

            if "duration_minutes" in fields:
                dur = _validate_duration(fields["duration_minutes"])
                set_clauses.append("duration_minutes = ?")
                params.append(dur)

            if "description" in fields:
                desc = _validate_description(fields["description"])
                set_clauses.append("description = ?")
                params.append(desc)

            if not set_clauses:
                # 변경 필드 없음 — 기존 Event 그대로 반환
                logger.warning("update_event: no fields to update for id=%d", event_id)
                return existing

            params.append(event_id)
            sql = f"UPDATE events SET {', '.join(set_clauses)} WHERE id = ?"  # noqa: S608

            try:
                conn.execute(sql, params)
            except sqlite3.Error as exc:
                raise CalendarDBError(f"UPDATE failed: {exc}") from exc

            logger.info(
                "CalendarService.update_event: id=%d fields=%r", event_id, list(fields.keys())
            )

            updated = self.get_event(event_id)
            assert updated is not None  # 방금 전 존재 확인했으므로
            return updated

    def delete_event(self, event_id: int) -> bool:
        """이벤트를 삭제한다. 하드 삭제.

        Args:
            event_id: 삭제할 이벤트 id.

        Returns:
            True if deleted, False if event_id not found.

        Raises:
            CalendarDBError: SQLite 오류.
        """
        with self._lock:
            conn = self._require_open()
            try:
                cursor = conn.execute("DELETE FROM events WHERE id = ?", (event_id,))
            except sqlite3.Error as exc:
                raise CalendarDBError(f"DELETE failed: {exc}") from exc

            deleted = cursor.rowcount > 0
            if deleted:
                logger.info("CalendarService.delete_event: id=%d deleted", event_id)
            else:
                logger.debug("CalendarService.delete_event: id=%d not found", event_id)
            return deleted

    def events_due_within(self, minutes: int) -> list[Event]:
        """``[now_utc, now_utc + minutes]`` 구간에 시작하는 이벤트를 반환한다.

        이미 지난 이벤트(start < now)는 제외된다.

        Args:
            minutes: 조회 범위(분). 1 이상이어야 한다.

        Returns:
            Event 리스트 (start ASC).

        Raises:
            CalendarValidationError: minutes < 1.
            CalendarDBError: SQLite 오류.
        """
        if not isinstance(minutes, int) or isinstance(minutes, bool) or minutes < 1:
            raise CalendarValidationError(f"minutes must be >= 1, got {minutes!r}")

        with self._lock:
            conn = self._require_open()

            now_utc = _now_utc()
            upper_utc = now_utc + timedelta(minutes=minutes)

            try:
                rows = conn.execute(
                    "SELECT id, title, start_utc, duration_minutes, description, created_at_utc "
                    "FROM events "
                    "WHERE start_utc >= ? AND start_utc <= ? "
                    "ORDER BY start_utc ASC",
                    (now_utc.isoformat(), upper_utc.isoformat()),
                ).fetchall()
            except sqlite3.Error as exc:
                raise CalendarDBError(f"SELECT (events_due_within) failed: {exc}") from exc

            return [_row_to_event(row, self.default_tz) for row in rows]

    def close(self) -> None:
        """DB 연결을 닫는다. 멱등성 보장.

        WAL checkpoint 후 연결 종료. 이미 닫힌 상태에서 재호출 시 no-op.
        어떤 예외도 밖으로 던지지 않는다.
        """
        with self._lock:
            if self._conn is None:
                return
            try:
                self._conn.execute("PRAGMA wal_checkpoint(FULL)")
                self._conn.close()
                logger.info("CalendarService: DB connection closed")
            except Exception as exc:  # noqa: BLE001
                logger.warning("CalendarService.close: error during close: %s", exc)
            finally:
                self._conn = None
