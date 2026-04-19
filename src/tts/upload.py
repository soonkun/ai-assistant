# src/tts/upload.py
"""화자 참조 WAV 업로드 HTTP 라우터."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from fastapi import APIRouter, HTTPException, Response, UploadFile
from pydantic import BaseModel

from .speaker_wav import validate_speaker_wav

logger = logging.getLogger(__name__)


class SpeakerWavUploadResponse(BaseModel):
    """POST 응답 스키마."""

    id: str  # sha256 prefix 16자
    path: str  # 서버 로컬 저장 절대 경로
    duration_sec: float
    sample_rate: int
    channels: int


class SpeakerWavListItem(BaseModel):
    """목록 아이템 스키마."""

    id: str
    path: str
    duration_sec: float
    sample_rate: int
    created_at: str  # ISO8601


def _sanitize_filename(filename: str) -> str:
    """파일명에서 경로 조작 문자를 제거하고 basename만 반환한다."""
    # Path.name으로 basename 추출 후 위험 문자 제거
    safe = Path(filename).name
    # 추가로 ..과 슬래시 제거 (Path.name이 이미 처리하지만 명시적으로)
    safe = safe.replace("..", "").replace("/", "").replace("\\", "")
    if not safe:
        safe = "upload.wav"
    return safe


def create_speaker_upload_router(
    storage_dir: str,
    max_bytes: int = 10 * 1024 * 1024,
    is_active_callback: Callable[[str], bool] | None = None,
) -> APIRouter:
    """M_01 FastAPI 앱에 포함될 화자 참조 WAV 업로드 라우터를 생성한다.

    엔드포인트:
      POST   /api/tts/speaker-refs
      GET    /api/tts/speaker-refs
      GET    /api/tts/speaker-refs/{id}
      DELETE /api/tts/speaker-refs/{id}

    Args:
        storage_dir: WAV 파일을 저장할 디렉토리 경로.
        max_bytes: 업로드 최대 크기(바이트). 기본 10MB.
        is_active_callback: 주어진 파일 경로가 현재 활성 엔진에서 사용 중인지
            확인하는 콜백. None이면 항상 inactive로 간주.

    Returns:
        APIRouter: FastAPI 라우터 인스턴스.
    """
    router = APIRouter(prefix="/api/tts/speaker-refs", tags=["tts"])

    def _ensure_storage_dir() -> None:
        os.makedirs(storage_dir, exist_ok=True, mode=0o700)

    def _scan_storage() -> list[SpeakerWavListItem]:
        """storage_dir의 .wav 파일을 스캔해 수정시각 내림차순 목록으로 반환한다."""
        storage_path = Path(storage_dir)
        if not storage_path.exists():
            return []
        items: list[SpeakerWavListItem] = []
        for wav_file in storage_path.glob("*.wav"):
            # tmp_ 접두사 파일은 제외
            if wav_file.name.startswith("tmp_"):
                continue
            # 파일명에서 id 추출: <id>_<name>.wav 형식
            stem = wav_file.stem  # 확장자 제외
            wav_id = stem[:16] if len(stem) >= 16 else stem
            mtime = wav_file.stat().st_mtime
            modified_iso = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()
            try:
                wav_info = validate_speaker_wav(str(wav_file))
                items.append(
                    SpeakerWavListItem(
                        id=wav_id,
                        path=str(wav_file.resolve()),
                        duration_sec=wav_info.duration_sec,
                        sample_rate=wav_info.sample_rate,
                        created_at=modified_iso,
                    )
                )
            except (ValueError, FileNotFoundError):
                # 검증 실패 파일은 목록에서 제외
                logger.warning("skipping invalid wav in storage: %s", wav_file)
        items.sort(key=lambda x: x.created_at, reverse=True)
        return items

    def _find_by_id(wav_id: str) -> SpeakerWavListItem | None:
        """id로 파일을 찾아 SpeakerWavListItem을 반환한다. 없으면 None."""
        for item in _scan_storage():
            if item.id == wav_id:
                return item
        return None

    @router.post("", response_model=SpeakerWavUploadResponse)
    async def upload_speaker_wav(file: UploadFile) -> SpeakerWavUploadResponse:
        """화자 참조 WAV 파일을 업로드한다."""
        _ensure_storage_dir()

        # 1. Content-Length 선검사 (헤더가 있는 경우)
        content_length = file.size
        if content_length is not None and content_length > max_bytes:
            raise HTTPException(status_code=413, detail="file too large")

        # 2. 확장자 검사
        filename = file.filename or "upload.wav"
        if not filename.lower().endswith(".wav"):
            raise HTTPException(status_code=400, detail="only .wav files are accepted")

        # 3. 안전한 파일명 생성 (경로 조작 방지)
        safe_name = _sanitize_filename(filename)

        # 임시 경로에 스트리밍 저장
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        tmp_path = Path(storage_dir) / f"tmp_{timestamp}_{safe_name}"

        accumulated = 0
        try:
            with tmp_path.open("wb") as f:
                while True:
                    chunk = await file.read(65536)
                    if not chunk:
                        break
                    accumulated += len(chunk)
                    if accumulated > max_bytes:
                        # 크기 초과: 임시 파일 삭제 후 413
                        f.close()
                        if tmp_path.exists():
                            tmp_path.unlink()
                        raise HTTPException(status_code=413, detail="file too large")
                    f.write(chunk)
        except HTTPException:
            raise
        except OSError as exc:
            if tmp_path.exists():
                tmp_path.unlink()
            logger.error("upload write failed: %s", exc)
            raise HTTPException(status_code=500, detail="File save failed")

        # 4. validate_speaker_wav
        try:
            wav_info = validate_speaker_wav(str(tmp_path))
        except (ValueError, FileNotFoundError) as exc:
            if tmp_path.exists():
                tmp_path.unlink()
            logger.warning("speaker wav validation failed: %s", exc)
            raise HTTPException(status_code=400, detail=str(exc))

        # 5. sha256 중복 확인 (디렉토리 스캔으로 재시작 후에도 동작)
        sha256 = wav_info.sha256
        wav_id = sha256[:16]

        existing_files = list(Path(storage_dir).glob(f"{wav_id}_*.wav"))
        if existing_files:
            # 이미 존재하는 파일 — 임시 파일 삭제 후 기존 파일 재사용
            if tmp_path.exists():
                tmp_path.unlink()
            existing_path = existing_files[0]
            existing = _find_by_id(wav_id)
            logger.info("duplicate sha256 detected, reusing id=%s", wav_id)
            if existing is not None:
                return SpeakerWavUploadResponse(
                    id=wav_id,
                    path=existing.path,
                    duration_sec=existing.duration_sec,
                    sample_rate=existing.sample_rate,
                    channels=wav_info.channels,
                )
            return SpeakerWavUploadResponse(
                id=wav_id,
                path=str(existing_path.resolve()),
                duration_sec=wav_info.duration_sec,
                sample_rate=wav_info.sample_rate,
                channels=wav_info.channels,
            )

        # 6. 최종 저장 경로로 이동
        final_path = Path(storage_dir) / f"{wav_id}_{safe_name}"
        tmp_path.rename(final_path)

        logger.info("speaker wav uploaded: id=%s path=%s", wav_id, final_path)
        return SpeakerWavUploadResponse(
            id=wav_id,
            path=str(final_path.resolve()),
            duration_sec=wav_info.duration_sec,
            sample_rate=wav_info.sample_rate,
            channels=wav_info.channels,
        )

    @router.get("", response_model=list[SpeakerWavListItem])
    async def list_speaker_wavs() -> list[SpeakerWavListItem]:
        """저장된 화자 참조 WAV 목록을 디렉토리 스캔으로 반환한다(수정시각 내림차순)."""
        return _scan_storage()

    @router.get("/{wav_id}", response_model=SpeakerWavListItem)
    async def get_speaker_wav(wav_id: str) -> SpeakerWavListItem:
        """특정 화자 참조 WAV 메타를 반환한다."""
        item = _find_by_id(wav_id)
        if item is None:
            raise HTTPException(status_code=404, detail=f"speaker ref not found: {wav_id}")
        return item

    @router.delete("/{wav_id}", status_code=204, response_class=Response)
    async def delete_speaker_wav(wav_id: str) -> Response:
        """화자 참조 WAV를 삭제한다."""
        item = _find_by_id(wav_id)
        if item is None:
            raise HTTPException(status_code=404, detail=f"speaker ref not found: {wav_id}")

        # 현재 활성 엔진에서 사용 중인지 확인
        if is_active_callback is not None and is_active_callback(item.path):
            raise HTTPException(
                status_code=409,
                detail="speaker ref is currently active",
            )

        # 파일 삭제
        file_path = Path(item.path)
        if file_path.exists():
            try:
                file_path.unlink()
            except OSError as exc:
                logger.error("Failed to delete speaker wav file %s: %s", item.path, exc)
                raise HTTPException(status_code=500, detail="File delete failed")

        logger.info("speaker wav deleted: id=%s", wav_id)
        return Response(status_code=204)

    return router
