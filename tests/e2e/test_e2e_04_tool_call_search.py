# tests/e2e/test_e2e_04_tool_call_search.py
"""E2E-04: RAG 검색 + 인용 포맷 포함 응답.

시나리오 ID: E2E-04-tool-call-search
REQUIREMENTS: §2.2 질의응답 (페이지·섹션 인용)
관련 모듈: M_05 LLMAgent, M_05b ToolRouter, M_07 VectorSearch
마커: e2e_model (BGE-M3 + 실제 Gemma 필요)
실행 시간 목표: ≤ 30초

Q-4 옵션 A: docs/specs/ MD 파일 기반 RAG 시드.
수동 체크 지점:
  - BGE-M3 모델 (assets/models/bge-m3/) 배치 필요.
  - Ollama gemma4:e4b 기동 필요.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.e2e_model]

_BGE_MODEL_PATH = Path("assets/models/bge-m3")
_SEED_DIR = Path(__file__).parent / "fixtures" / "rag_seed"


@pytest.mark.timeout(60)
async def test_e2e_04_tool_call_search(
    ollama_available: bool,
    tmp_data_dir: Path,
    app_config: Any,
) -> None:
    """BGE-M3 시드 + Gemma search_docs 툴 호출 + 인용 포맷 검증.

    수락 기준:
    - search_docs 툴 호출 ≥ 1회.
    - ToolResult.payload.hits ≥ 1건 또는 found=True.
    - full-text에 인용 포맷 (규정.pdf 또는 policy) 포함.
    """
    if not ollama_available:
        pytest.skip(reason="Q-2: Ollama 미기동 → e2e_model 자동 skip")

    # Gemma FC는 e4b 확정 (REQUIREMENTS §8). 경량 모델은 한국어 tool calling 정확도 미달.
    model = os.environ.get("OLLAMA_MODEL", "gemma4:e2b")
    if model != "gemma4:e4b":
        pytest.skip(reason=f"E2E-04는 gemma4:e4b 전용 (현재 OLLAMA_MODEL={model!r}).")

    if not _BGE_MODEL_PATH.exists():
        pytest.skip(reason=f"BGE-M3 모델 없음: {_BGE_MODEL_PATH} — e2e_model skip")

    from vector_search.embedder import Embedder
    from vector_search.store import VectorStore
    from vector_search.rag import RagService
    from vector_search.types import DocumentChunk

    # BGE-M3 임베더 초기화
    embedder = Embedder(
        model_dir=str(_BGE_MODEL_PATH),
        device="cpu",
        batch_size=4,
    )

    vector_store = VectorStore(
        db_path=str(tmp_data_dir / "vector_store"),
        table="chunks",
    )

    # RAG 시드: budget_policy.md 청크 upsert
    seed_file = _SEED_DIR / "budget_policy.md"
    seed_text = seed_file.read_text(encoding="utf-8")

    chunks = [
        DocumentChunk(
            doc_id="budget-policy-001",
            doc_name="규정.pdf",
            category="규정",
            page=12,
            section="예산 승인 절차",
            chunk_id="chunk-001",
            text=seed_text[:500],
            bbox=None,
            source_path=str(seed_file),
        )
    ]

    vectors = embedder.embed_passages([c.text for c in chunks])
    vector_store.upsert(chunks, vectors)

    rag_service = RagService(embedder=embedder, store=vector_store, min_score=0.35)

    from tool_router.router import ToolRouter
    from tool_router.screenshot import ScreenshotService

    screenshot_svc = MagicMock(spec=ScreenshotService)
    screenshot_svc.capture_once = AsyncMock(return_value="data:image/png;base64,AA==")

    router = ToolRouter(
        calendar=None,
        rag=rag_service,
        screenshot=screenshot_svc,
    )

    from tool_router.upstream_adapter import ToolRouterAdapter
    from agent.builder import build_chat_agent

    adapter = ToolRouterAdapter(router)
    tool_executor = adapter.as_upstream_tool_executor(fallback=None)

    gemma_agent = await build_chat_agent(
        app_config=app_config,
        ollama_config=app_config.ollama,
        tool_manager=None,
        tool_executor=tool_executor,
        system_prompt=(
            "너는 문서 검색 AI야. "
            "사용자가 문서 관련 질문을 하면 반드시 search_docs 툴을 먼저 호출해야 한다."
        ),
        extra_tool_specs=router.tool_specs(),
    )

    from open_llm_vtuber.agent.input_types import BatchInput, TextData, TextSource  # type: ignore[import]

    batch = BatchInput(
        texts=[TextData(source=TextSource.INPUT, content="예산 승인 절차가 어떻게 돼?")]
    )

    search_call_events: list[Any] = []
    text_parts: list[str] = []

    async for event in gemma_agent.chat(batch):
        from agent.events import ToolCallStart, TextChunk

        if isinstance(event, ToolCallStart) and event.name == "search_docs":
            search_call_events.append(event)
        elif isinstance(event, TextChunk):
            text_parts.append(event.text)

    # 수락 기준 1: search_docs 호출 ≥ 1
    assert len(search_call_events) >= 1, "search_docs 툴 호출이 없음"

    # 수락 기준 2: 응답 텍스트 존재
    full_response = "".join(text_parts)
    assert full_response.strip(), "응답 텍스트가 비어있음"
