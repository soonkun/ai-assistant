# tests/tts/test_upload_router.py
"""화자 참조 WAV 업로드 라우터 단위 테스트."""

from __future__ import annotations

import io
import wave
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tts.upload import create_speaker_upload_router


def _create_wav_bytes(
    duration_sec: float = 4.0,
    sample_rate: int = 24000,
    channels: int = 1,
    sampwidth: int = 2,
) -> bytes:
    """인메모리 WAV 바이트 생성."""
    buf = io.BytesIO()
    n_frames = int(duration_sec * sample_rate)
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00" * (n_frames * channels * sampwidth))
    return buf.getvalue()


@pytest.fixture()
def storage_dir(tmp_path: Path) -> Path:
    """테스트용 스토리지 디렉토리."""
    return tmp_path / "speaker_refs"


@pytest.fixture()
def client(storage_dir: Path) -> TestClient:
    """테스트용 FastAPI 앱 + TestClient."""
    app = FastAPI()
    router = create_speaker_upload_router(storage_dir=str(storage_dir))
    app.include_router(router)
    return TestClient(app)


@pytest.fixture()
def client_with_active_callback(tmp_path: Path) -> tuple[TestClient, Path]:
    """활성 콜백이 있는 TestClient와 storage_dir를 반환."""
    storage = tmp_path / "speaker_refs"
    storage.mkdir()
    app = FastAPI()

    # 업로드 후 is_active_callback이 해당 파일을 "활성"으로 반환하는 라우터
    _active_paths: list[str] = []

    def is_active(path: str) -> bool:
        return path in _active_paths

    router = create_speaker_upload_router(
        storage_dir=str(storage),
        is_active_callback=is_active,
    )
    app.include_router(router)
    tc = TestClient(app)
    # 한 번 업로드해 _active_paths에 등록
    wav_bytes = _create_wav_bytes()
    resp = tc.post(
        "/api/tts/speaker-refs",
        files={"file": ("voice.wav", io.BytesIO(wav_bytes), "audio/wav")},
    )
    assert resp.status_code == 200
    saved_path = resp.json()["path"]
    _active_paths.append(saved_path)
    return tc, storage


# ---------------------------------------------------------------------------
# 정상 케이스 N-7
# ---------------------------------------------------------------------------


class TestUploadRouterNormal:
    def test_post_valid_wav(self, client: TestClient, tmp_path: Path) -> None:
        """N-7: 유효한 WAV 업로드 → 200, id 16자, 저장 파일 존재."""
        wav_bytes = _create_wav_bytes()
        resp = client.post(
            "/api/tts/speaker-refs",
            files={"file": ("voice.wav", io.BytesIO(wav_bytes), "audio/wav")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["id"]) == 16
        assert Path(data["path"]).exists()
        assert data["duration_sec"] > 0

    def test_post_duplicate_returns_same_id(self, client: TestClient) -> None:
        """E-7 / N-7: 동일 파일 두 번 업로드 → 같은 id, 디스크에 1개."""
        wav_bytes = _create_wav_bytes()

        resp1 = client.post(
            "/api/tts/speaker-refs",
            files={"file": ("voice.wav", io.BytesIO(wav_bytes), "audio/wav")},
        )
        resp2 = client.post(
            "/api/tts/speaker-refs",
            files={"file": ("voice.wav", io.BytesIO(wav_bytes), "audio/wav")},
        )
        assert resp1.status_code == 200
        assert resp2.status_code == 200
        assert resp1.json()["id"] == resp2.json()["id"]
        # 동일 경로 → 실제 파일 1개
        assert resp1.json()["path"] == resp2.json()["path"]

    def test_list_wavs(self, client: TestClient) -> None:
        """GET /api/tts/speaker-refs → 목록 반환."""
        wav_bytes = _create_wav_bytes()
        client.post(
            "/api/tts/speaker-refs",
            files={"file": ("voice.wav", io.BytesIO(wav_bytes), "audio/wav")},
        )
        resp = client.get("/api/tts/speaker-refs")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
        assert len(resp.json()) >= 1

    def test_get_wav_by_id(self, client: TestClient) -> None:
        """GET /api/tts/speaker-refs/{id} → 메타 반환."""
        wav_bytes = _create_wav_bytes()
        post_resp = client.post(
            "/api/tts/speaker-refs",
            files={"file": ("voice.wav", io.BytesIO(wav_bytes), "audio/wav")},
        )
        wav_id = post_resp.json()["id"]
        resp = client.get(f"/api/tts/speaker-refs/{wav_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == wav_id

    def test_delete_wav(self, client: TestClient, tmp_path: Path) -> None:
        """DELETE /api/tts/speaker-refs/{id} → 204, 파일 삭제."""
        wav_bytes = _create_wav_bytes()
        post_resp = client.post(
            "/api/tts/speaker-refs",
            files={"file": ("voice.wav", io.BytesIO(wav_bytes), "audio/wav")},
        )
        wav_id = post_resp.json()["id"]
        saved_path = post_resp.json()["path"]

        resp = client.delete(f"/api/tts/speaker-refs/{wav_id}")
        assert resp.status_code == 204
        assert not Path(saved_path).exists()

    def test_boundary_sample_rate_22050(self, client: TestClient) -> None:
        """E-5: 22050Hz WAV 업로드 → 200, sample_rate=22050."""
        wav_bytes = _create_wav_bytes(duration_sec=3.0, sample_rate=22050)
        resp = client.post(
            "/api/tts/speaker-refs",
            files={"file": ("22k.wav", io.BytesIO(wav_bytes), "audio/wav")},
        )
        assert resp.status_code == 200
        assert resp.json()["sample_rate"] == 22050

    def test_upload_file_size_none(self, storage_dir: Path) -> None:
        """C-9: file.size=None인 경우 accumulator(chunk-by-chunk) 경로 → 200, 파일 저장.

        SpooledTemporaryFile 기반 mock으로 file.size=None 시뮬레이션.
        upload_speaker_wav 엔드포인트를 직접 호출해 accumulator 경로를 검증한다.
        """
        import asyncio

        from fastapi import UploadFile

        wav_bytes = _create_wav_bytes()

        # file.size = None인 mock UploadFile 생성
        mock_file = MagicMock(spec=UploadFile)
        mock_file.size = None  # accumulator 경로 진입
        mock_file.filename = "voice_no_size.wav"

        # read()를 청크로 반환 (65536 단위 + 빈 bytes로 종료)
        chunks = list(wav_bytes[i : i + 65536] for i in range(0, len(wav_bytes), 65536))
        chunks.append(b"")
        chunk_iter = iter(chunks)

        async def mock_read(n: int = -1) -> bytes:
            return next(chunk_iter, b"")

        mock_file.read = mock_read

        # 라우터의 POST 핸들러를 직접 추출해 비동기 호출
        storage = str(storage_dir)
        _app = FastAPI()
        _router = create_speaker_upload_router(storage_dir=storage)
        _app.include_router(_router)

        # POST 핸들러는 라우터 내부 클로저이므로 TestClient 경유가 가장 안정적.
        # file.size=None을 TestClient가 덮어쓰지 않도록 직접 asyncio 호출.
        upload_fn = None
        for route in _router.routes:
            if (
                hasattr(route, "path")
                and "speaker-refs" in route.path
                and "{" not in route.path  # path parameter 없는 것
                and "POST" in getattr(route, "methods", set())
            ):  # type: ignore[union-attr]
                upload_fn = route.endpoint  # type: ignore[union-attr]
                break

        assert upload_fn is not None, "POST 핸들러를 찾지 못했습니다"

        storage_dir.mkdir(exist_ok=True)
        result = asyncio.run(upload_fn(file=mock_file))

        assert result.id is not None and len(result.id) == 16
        assert Path(result.path).exists()


# ---------------------------------------------------------------------------
# 에러 케이스
# ---------------------------------------------------------------------------


class TestUploadRouterErrors:
    def test_oversized_file_413(self, tmp_path: Path) -> None:
        """A-5: 10MB 초과 파일 → HTTP 413, 디스크에 파일 없음."""
        storage_dir = tmp_path / "sr2"
        storage = str(storage_dir)
        app = FastAPI()
        router = create_speaker_upload_router(storage_dir=storage, max_bytes=1024)
        app.include_router(router)
        tc = TestClient(app)

        # max_bytes=1024보다 큰 페이로드 전송 (유효한 WAV 헤더 없이 충분히 큰 데이터)
        big_data = b"\x00" * 2048
        resp = tc.post(
            "/api/tts/speaker-refs",
            files={"file": ("big.wav", io.BytesIO(big_data), "audio/wav")},
        )
        assert resp.status_code == 413
        # 디스크에 파일이 저장되지 않았음을 확인
        assert not any(storage_dir.glob("*.wav"))

    def test_oversized_accumulator_413(self, tmp_path: Path) -> None:
        """M15: file.size=None이지만 청크 누적 후 max_bytes 초과 → 413, 디스크 파일 없음."""
        import asyncio

        from fastapi import UploadFile
        from unittest.mock import MagicMock

        storage_dir = tmp_path / "sr_acc"
        storage = str(storage_dir)

        # max_bytes=100 설정
        _router = create_speaker_upload_router(storage_dir=storage, max_bytes=100)
        upload_fn = None
        for route in _router.routes:
            if (
                hasattr(route, "path")
                and "speaker-refs" in route.path
                and "{" not in route.path
                and "POST" in getattr(route, "methods", set())
            ):
                upload_fn = route.endpoint
                break
        assert upload_fn is not None

        # 150바이트를 두 청크로 반환, size=None
        mock_file = MagicMock(spec=UploadFile)
        mock_file.size = None
        mock_file.filename = "big_stream.wav"

        chunks = [b"\x00" * 80, b"\x00" * 70, b""]
        chunk_iter = iter(chunks)

        async def mock_read(n: int = -1) -> bytes:
            return next(chunk_iter, b"")

        mock_file.read = mock_read

        storage_dir.mkdir(exist_ok=True)

        import pytest
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            asyncio.run(upload_fn(file=mock_file))

        assert exc_info.value.status_code == 413
        assert not any(storage_dir.glob("*.wav"))

    def test_invalid_wav_header_400(self, client: TestClient) -> None:
        """A-6: MP3 바이트에 .wav 확장자 → HTTP 400."""
        fake_wav = b"ID3" + b"\x00" * 200  # MP3 헤더
        resp = client.post(
            "/api/tts/speaker-refs",
            files={"file": ("fake.wav", io.BytesIO(fake_wav), "audio/wav")},
        )
        assert resp.status_code == 400

    def test_wrong_extension_400(self, client: TestClient) -> None:
        """확장자 .mp3 → HTTP 400."""
        resp = client.post(
            "/api/tts/speaker-refs",
            files={"file": ("audio.mp3", io.BytesIO(b"\x00" * 512), "audio/mpeg")},
        )
        assert resp.status_code == 400

    def test_path_traversal_prevention(self, client: TestClient, tmp_path: Path) -> None:
        """A-7: filename='../../etc/passwd.wav' → 200, 저장 파일이 storage_dir 하위에 있음."""
        storage_dir = tmp_path / "speaker_refs"
        wav_bytes = _create_wav_bytes()
        resp = client.post(
            "/api/tts/speaker-refs",
            files={"file": ("../../etc/passwd.wav", io.BytesIO(wav_bytes), "audio/wav")},
        )
        assert resp.status_code == 200
        saved_path = resp.json()["path"]
        # 저장 경로가 storage_dir 하위여야 한다
        assert Path(saved_path).resolve().is_relative_to(storage_dir.resolve())
        # 경로에 '..' 없음
        assert ".." not in saved_path

    def test_get_not_found_404(self, client: TestClient) -> None:
        """존재하지 않는 id 조회 → 404."""
        resp = client.get("/api/tts/speaker-refs/nonexistent000000")
        assert resp.status_code == 404

    def test_delete_not_found_404(self, client: TestClient) -> None:
        """존재하지 않는 id 삭제 → 404."""
        resp = client.delete("/api/tts/speaker-refs/nonexistent000000")
        assert resp.status_code == 404

    def test_delete_active_ref_409(
        self, client_with_active_callback: tuple[TestClient, Path]
    ) -> None:
        """DELETE 활성 엔진이 사용 중인 파일 → 409."""
        tc, _ = client_with_active_callback
        # 현재 등록된 첫 번째 항목 가져오기
        list_resp = tc.get("/api/tts/speaker-refs")
        assert list_resp.status_code == 200
        items = list_resp.json()
        assert len(items) >= 1
        wav_id = items[0]["id"]

        resp = tc.delete(f"/api/tts/speaker-refs/{wav_id}")
        assert resp.status_code == 409
        assert "active" in resp.json()["detail"].lower()
