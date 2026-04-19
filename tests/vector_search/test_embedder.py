# tests/vector_search/test_embedder.py
"""Embedder 테스트: FakeEmbedder 기반 (N-7, A-6) + 실모델 smoke @slow (S-1).

추가: unittest.mock 기반 Embedder 생성자·추론 경로 커버리지 테스트.
"""

from __future__ import annotations

import os
import sys
import types
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from tests.vector_search.fakes import FakeEmbedder
from vector_search.errors import EmbedderError


def _install_fake_sentence_transformers() -> MagicMock:
    """sentence_transformers 모듈이 설치되지 않았거나 import 오류 시
    sys.modules에 가짜 모듈을 등록하고 MagicMock SentenceTransformer 클래스를 반환."""
    mock_st_cls = MagicMock(name="SentenceTransformer")
    fake_module = types.ModuleType("sentence_transformers")
    fake_module.SentenceTransformer = mock_st_cls  # type: ignore[attr-defined]
    sys.modules["sentence_transformers"] = fake_module
    return mock_st_cls


def _restore_sentence_transformers(original: Any) -> None:
    """테스트 종료 후 sys.modules 원상복구."""
    if original is None:
        sys.modules.pop("sentence_transformers", None)
    else:
        sys.modules["sentence_transformers"] = original


class TestFakeEmbedder:
    """FakeEmbedder 자체 동작 검증."""

    def test_embed_passages_shape(self) -> None:
        fe = FakeEmbedder()
        result = fe.embed_passages(["hello", "world", "테스트"])
        assert result.shape == (3, 1024)
        assert result.dtype == np.float32

    def test_embed_passages_empty_list(self) -> None:
        """N-7: embed_passages([]) → shape (0, 1024) float32."""
        fe = FakeEmbedder()
        result = fe.embed_passages([])
        assert result.shape == (0, 1024)
        assert result.dtype == np.float32

    def test_embed_query_shape(self) -> None:
        fe = FakeEmbedder()
        result = fe.embed_query("안녕하세요")
        assert result.shape == (1024,)
        assert result.dtype == np.float32

    def test_deterministic(self) -> None:
        """동일 텍스트 → 동일 벡터."""
        fe = FakeEmbedder()
        v1 = fe.embed_query("테스트 문장")
        v2 = fe.embed_query("테스트 문장")
        np.testing.assert_array_equal(v1, v2)

    def test_different_texts_different_vecs(self) -> None:
        fe = FakeEmbedder()
        v1 = fe.embed_query("문장 A")
        v2 = fe.embed_query("문장 B")
        assert not np.allclose(v1, v2)

    def test_l2_normalized(self) -> None:
        """L2 정규화: norm ≈ 1.0."""
        fe = FakeEmbedder()
        vec = fe.embed_query("정규화 테스트")
        norm = float(np.linalg.norm(vec))
        assert abs(norm - 1.0) < 1e-5

    def test_embed_passages_l2_normalized(self) -> None:
        fe = FakeEmbedder()
        result = fe.embed_passages(["a", "b", "c"])
        norms = np.linalg.norm(result, axis=1)
        np.testing.assert_allclose(norms, 1.0, atol=1e-5)


class TestNanInjection:
    """A-6: NaN/Inf 벡터 삽입 방어 (monkeypatch로 Embedder._try_encode를 NaN 반환으로 교체)."""

    def test_nan_in_embedder_raises_embedder_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Embedder가 NaN 벡터를 반환하면 EmbedderError를 raise해야 한다."""
        import numpy as np

        from vector_search.embedder import Embedder

        # config.json이 없으므로 __init__을 통하지 않고 인스턴스를 직접 생성
        embedder = object.__new__(Embedder)
        embedder._batch_size = 32  # type: ignore[attr-defined]
        embedder._normalize = True  # type: ignore[attr-defined]
        embedder._device = "cpu"  # type: ignore[attr-defined]

        # _try_encode가 NaN 벡터를 반환하도록 monkeypatch
        nan_vec = np.full((1, 1024), float("nan"), dtype=np.float32)
        monkeypatch.setattr(embedder, "_try_encode", lambda texts: nan_vec)

        with pytest.raises(EmbedderError, match="NaN/Inf"):
            embedder.embed_passages(["test"])

    def test_inf_in_embedder_raises_embedder_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import numpy as np

        from vector_search.embedder import Embedder

        embedder = object.__new__(Embedder)
        embedder._batch_size = 32  # type: ignore[attr-defined]
        embedder._normalize = True  # type: ignore[attr-defined]
        embedder._device = "cpu"  # type: ignore[attr-defined]

        inf_vec = np.full((1, 1024), float("inf"), dtype=np.float32)
        monkeypatch.setattr(embedder, "_try_encode", lambda texts: inf_vec)

        with pytest.raises(EmbedderError, match="NaN/Inf"):
            embedder.embed_passages(["test"])


# ---- mock 기반 Embedder 경로 커버리지 테스트 ----


def _make_model_dir(tmp_path: Path) -> Path:
    """테스트용 가짜 model 디렉터리 생성 (config.json 포함)."""
    model_dir = tmp_path / "bge-m3"
    model_dir.mkdir()
    (model_dir / "config.json").write_text("{}")
    return model_dir


@pytest.fixture()
def fake_st_module() -> Any:
    """sentence_transformers 모듈을 가짜 모듈로 교체하는 fixture.

    sentence_transformers 실 패키지가 soundfile 등 호환 이슈로 import 불가할 때도
    embedder 생성자 경로를 테스트할 수 있도록 sys.modules에 stub을 주입한다.
    테스트 종료 후 원래 상태로 복원.
    """
    original = sys.modules.get("sentence_transformers")
    mock_cls = MagicMock(name="SentenceTransformer")
    fake_mod = types.ModuleType("sentence_transformers")
    fake_mod.SentenceTransformer = mock_cls  # type: ignore[attr-defined]
    sys.modules["sentence_transformers"] = fake_mod
    yield mock_cls
    if original is None:
        sys.modules.pop("sentence_transformers", None)
    else:
        sys.modules["sentence_transformers"] = original


class TestEmbedderConstructorMock:
    """Embedder 생성자 경로를 SentenceTransformer mock으로 커버."""

    def test_constructor_calls_sentence_transformer_with_correct_args(
        self, tmp_path: Path, fake_st_module: MagicMock
    ) -> None:
        """MT-1: SentenceTransformer가 model_path·device·local_files_only 인자로 호출."""
        model_dir = _make_model_dir(tmp_path)

        from vector_search.embedder import Embedder

        embedder = Embedder(model_dir=str(model_dir), device="cpu")

        fake_st_module.assert_called_once_with(
            str(model_dir),
            device="cpu",
            local_files_only=True,
            cache_folder=None,
        )
        assert embedder._device == "cpu"

    def test_offline_env_vars_set_on_constructor(
        self, tmp_path: Path, fake_st_module: MagicMock
    ) -> None:
        """MT-2: 생성자 호출 시 HF_HUB_OFFLINE, TRANSFORMERS_OFFLINE 환경변수가 세팅."""
        model_dir = _make_model_dir(tmp_path)

        # 기존 값을 백업하고 제거
        old_hf = os.environ.pop("HF_HUB_OFFLINE", None)
        old_tf = os.environ.pop("TRANSFORMERS_OFFLINE", None)
        try:
            from vector_search.embedder import Embedder

            Embedder(model_dir=str(model_dir), device="cpu")

            assert os.environ.get("HF_HUB_OFFLINE") == "1"
            assert os.environ.get("TRANSFORMERS_OFFLINE") == "1"
        finally:
            if old_hf is not None:
                os.environ["HF_HUB_OFFLINE"] = old_hf
            if old_tf is not None:
                os.environ["TRANSFORMERS_OFFLINE"] = old_tf

    def test_constructor_raises_embedder_error_when_model_path_missing(
        self, tmp_path: Path, fake_st_module: MagicMock
    ) -> None:
        """MT-3: model_path가 없으면 EmbedderError 발생."""
        from vector_search.embedder import Embedder

        with pytest.raises(EmbedderError, match="bge-m3 model not found"):
            Embedder(model_dir=str(tmp_path / "nonexistent"), device="cpu")

    def test_constructor_raises_embedder_error_when_config_json_missing(
        self, tmp_path: Path, fake_st_module: MagicMock
    ) -> None:
        """MT-4: 디렉터리는 있으나 config.json 없으면 EmbedderError 발생."""
        model_dir = tmp_path / "bge-m3-no-config"
        model_dir.mkdir()
        # config.json 없음

        from vector_search.embedder import Embedder

        with pytest.raises(EmbedderError, match="bge-m3 model not found"):
            Embedder(model_dir=str(model_dir), device="cpu")

    def test_constructor_raises_embedder_error_when_sentence_transformer_raises(
        self, tmp_path: Path, fake_st_module: MagicMock
    ) -> None:
        """MT-5: SentenceTransformer 생성자가 OSError 발생 시 EmbedderError로 래핑."""
        model_dir = _make_model_dir(tmp_path)
        fake_st_module.side_effect = OSError("모델 파일 없음")

        from vector_search.embedder import Embedder

        with pytest.raises(EmbedderError, match="모델 로드 실패"):
            Embedder(model_dir=str(model_dir), device="cpu")

    def test_constructor_raises_embedder_error_when_file_not_found(
        self, tmp_path: Path, fake_st_module: MagicMock
    ) -> None:
        """MT-6: SentenceTransformer 생성자가 FileNotFoundError 시 EmbedderError로 래핑."""
        model_dir = _make_model_dir(tmp_path)
        fake_st_module.side_effect = FileNotFoundError("가중치 파일 없음")

        from vector_search.embedder import Embedder

        with pytest.raises(EmbedderError, match="모델 로드 실패"):
            Embedder(model_dir=str(model_dir), device="cpu")


class TestEmbedderInferenceMock:
    """Embedder embed_passages / embed_query 경로를 mock encode로 커버."""

    def _make_embedder(self, tmp_path: Path, fake_st_cls: MagicMock, normalize: bool = True) -> Any:
        """fake_st_cls(fixture)를 주입한 Embedder 인스턴스 + mock _model 반환."""
        model_dir = _make_model_dir(tmp_path)
        mock_model = MagicMock()
        fake_st_cls.return_value = mock_model
        fake_st_cls.side_effect = None  # side_effect 초기화

        from vector_search.embedder import Embedder

        embedder = Embedder(model_dir=str(model_dir), device="cpu", normalize=normalize)
        return embedder, mock_model

    def test_embed_passages_normal_returns_float32_array(
        self, tmp_path: Path, fake_st_module: MagicMock
    ) -> None:
        """MT-7: mock encode가 (N, 1024) 반환 시 결과가 float32 ndarray."""
        embedder, mock_model = self._make_embedder(tmp_path, fake_st_module)
        fake_output = np.random.randn(3, 1024).astype(np.float32)
        mock_model.encode.return_value = fake_output

        result = embedder.embed_passages(["a", "b", "c"])

        assert result.shape == (3, 1024)
        assert result.dtype == np.float32
        mock_model.encode.assert_called_once()

    def test_embed_passages_normalized_output(
        self, tmp_path: Path, fake_st_module: MagicMock
    ) -> None:
        """MT-8: normalize=True 시 mock이 이미 정규화된 벡터 반환 → 그대로 유지."""
        embedder, mock_model = self._make_embedder(tmp_path, fake_st_module, normalize=True)
        raw = np.random.randn(2, 1024).astype(np.float32)
        normed = raw / np.linalg.norm(raw, axis=1, keepdims=True)
        mock_model.encode.return_value = normed

        result = embedder.embed_passages(["x", "y"])

        assert result.shape == (2, 1024)
        norms = np.linalg.norm(result, axis=1)
        np.testing.assert_allclose(norms, 1.0, atol=1e-5)

    def test_embed_passages_empty_list_returns_empty_array(
        self, tmp_path: Path, fake_st_module: MagicMock
    ) -> None:
        """MT-9: 빈 리스트 입력 시 shape (0, 1024) 반환, encode 미호출."""
        embedder, mock_model = self._make_embedder(tmp_path, fake_st_module)

        result = embedder.embed_passages([])

        assert result.shape == (0, 1024)
        assert result.dtype == np.float32
        mock_model.encode.assert_not_called()

    def test_embed_passages_inference_failure_raises_embedder_error(
        self, tmp_path: Path, fake_st_module: MagicMock
    ) -> None:
        """MT-10: encode 예외 발생(device=cpu) 시 EmbedderError 전파."""
        embedder, mock_model = self._make_embedder(tmp_path, fake_st_module)
        mock_model.encode.side_effect = RuntimeError("OOM")

        with pytest.raises(EmbedderError, match="embed_passages 추론 실패"):
            embedder.embed_passages(["text"])

    def test_embed_query_normal_returns_1d_array(
        self, tmp_path: Path, fake_st_module: MagicMock
    ) -> None:
        """MT-11: embed_query 정상 경로 - shape (1024,) float32."""
        embedder, mock_model = self._make_embedder(tmp_path, fake_st_module)
        fake_output = np.random.randn(1, 1024).astype(np.float32)
        mock_model.encode.return_value = fake_output

        result = embedder.embed_query("안녕하세요")

        assert result.shape == (1024,)
        assert result.dtype == np.float32

    def test_embed_query_empty_string_uses_space_placeholder(
        self, tmp_path: Path, fake_st_module: MagicMock
    ) -> None:
        """MT-12: 빈 문자열 입력 시 공백 1자로 치환 후 embed (ValueError 아님)."""
        embedder, mock_model = self._make_embedder(tmp_path, fake_st_module)
        fake_output = np.random.randn(1, 1024).astype(np.float32)
        mock_model.encode.return_value = fake_output

        result = embedder.embed_query("")

        assert result.shape == (1024,)
        call_args = mock_model.encode.call_args
        texts_arg: list[str] = call_args[0][0]
        assert texts_arg == [" "]

    def test_embed_passages_empty_string_in_list_replaced_by_space(
        self, tmp_path: Path, fake_st_module: MagicMock
    ) -> None:
        """MT-13: 리스트 내 빈 문자열이 공백 1자로 치환되어 encode에 전달."""
        embedder, mock_model = self._make_embedder(tmp_path, fake_st_module)
        fake_output = np.random.randn(2, 1024).astype(np.float32)
        mock_model.encode.return_value = fake_output

        embedder.embed_passages(["정상 텍스트", ""])

        call_args = mock_model.encode.call_args
        texts_arg: list[str] = call_args[0][0]
        assert texts_arg == ["정상 텍스트", " "]


class TestEmbedderDeviceResolutionMock:
    """_resolve_device 경로를 mock으로 커버."""

    def test_auto_device_falls_back_to_cpu_when_cuda_unavailable(
        self, tmp_path: Path, fake_st_module: MagicMock
    ) -> None:
        """MT-14: device='auto', CUDA 불가 → cpu로 fallback."""
        model_dir = _make_model_dir(tmp_path)
        fake_st_module.return_value = MagicMock()
        fake_st_module.side_effect = None

        with patch("torch.cuda.is_available", return_value=False):
            from vector_search.embedder import Embedder

            embedder = Embedder(model_dir=str(model_dir), device="auto")

        assert embedder._device == "cpu"

    def test_auto_device_selects_cuda_when_available(
        self, tmp_path: Path, fake_st_module: MagicMock
    ) -> None:
        """MT-15: device='auto', CUDA 가용 → cuda 선택."""
        model_dir = _make_model_dir(tmp_path)
        fake_st_module.return_value = MagicMock()
        fake_st_module.side_effect = None

        with (
            patch("torch.cuda.is_available", return_value=True),
            patch("torch.cuda.device_count", return_value=1),
        ):
            from vector_search.embedder import Embedder

            embedder = Embedder(model_dir=str(model_dir), device="auto")

        assert embedder._device == "cuda"

    def test_cuda_device_raises_when_cuda_unavailable(
        self, tmp_path: Path, fake_st_module: MagicMock
    ) -> None:
        """MT-16: device='cuda', CUDA 불가 → EmbedderError."""
        model_dir = _make_model_dir(tmp_path)
        fake_st_module.side_effect = None

        with (
            patch("torch.cuda.is_available", return_value=False),
            patch("torch.cuda.device_count", return_value=0),
        ):
            from vector_search.embedder import Embedder

            with pytest.raises(EmbedderError, match="CUDA 사용 불가"):
                Embedder(model_dir=str(model_dir), device="cuda")


# ---- 실모델 smoke 테스트 (기본 pytest 런에서 제외) ----


@pytest.mark.slow
def test_real_embedder_load_and_embed() -> None:
    """S-1: 실 BGE-M3 로드 + embed_query shape/dtype/norm 검증."""
    from vector_search.embedder import Embedder

    model_dir = "assets/models/bge-m3"
    embedder = Embedder(model_dir=model_dir, device="cpu")
    result = embedder.embed_query("안녕하세요")

    assert result.shape == (1024,)
    assert result.dtype == np.float32
    norm = float(np.linalg.norm(result))
    assert abs(norm - 1.0) < 1e-4, f"L2 norm = {norm}, 기대 ≈ 1.0"
