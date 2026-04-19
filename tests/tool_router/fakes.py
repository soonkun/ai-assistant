# tests/tool_router/fakes.py
"""FakeCalendarService, FakeRagService — 테스트용 Fake 구현체."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class FakeEvent:
    id: int
    title: str
    start: datetime
    duration_minutes: int
    description: str | None = None
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class FakeSearchHit:
    doc_name: str
    page: int | None
    section: str | None
    chunk_id: str
    text: str
    score: float


@dataclass
class FakeRetrievalResult:
    hits: list[FakeSearchHit]
    found: bool
    no_match_reason: str | None = None


class FakeCalendarService:
    """CalendarService 테스트 대역."""

    def __init__(self, events: list[FakeEvent] | None = None) -> None:
        self._events: list[FakeEvent] = events or []
        self.add_event_calls: list[dict[str, Any]] = []
        self.get_events_calls: list[dict[str, Any]] = []

    def add_event(
        self,
        title: str,
        start: datetime,
        duration_minutes: int,
        description: str | None = None,
    ) -> FakeEvent:
        self.add_event_calls.append(
            {
                "title": title,
                "start": start,
                "duration_minutes": duration_minutes,
                "description": description,
            }
        )
        event = FakeEvent(
            id=42,
            title=title,
            start=start,
            duration_minutes=duration_minutes,
            description=description,
        )
        self._events.append(event)
        return event

    def get_events(self, start: datetime, end: datetime) -> list[FakeEvent]:
        self.get_events_calls.append({"start": start, "end": end})
        return [e for e in self._events if start <= e.start <= end]


class FakeRagService:
    """RagService 테스트 대역."""

    def __init__(self, result: FakeRetrievalResult | None = None) -> None:
        self._result = result or FakeRetrievalResult(hits=[], found=False)
        self.retrieve_calls: list[dict[str, Any]] = []

    def retrieve(
        self,
        query: str,
        top_k: int,
        category: str | None = None,
    ) -> FakeRetrievalResult:
        self.retrieve_calls.append({"query": query, "top_k": top_k, "category": category})
        return self._result

    def format_citation(self, hit: FakeSearchHit) -> str:
        return f"`{hit.doc_name}` {hit.page}페이지, '{hit.section}' 섹션"
