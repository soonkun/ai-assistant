# src/vector_search/embedder.py
"""BGE-M3 로컬 로드 + 배치 임베딩 (M_07 §4.5, §6.1)."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import numpy as np

from .errors import EmbedderError

logger = logging.getLogger(__name__)


class Embedder:
    """BGE-M3 로컬 로드 + 배치 임베딩.

    동기 API로 확정한다. CPU 추론 자체가 blocking·CPU-bound이며, 호출자(RagService)가
    sync이므로 async 감싸기는 불필요.

    Args:
        model_dir: `assets/models/bge-m3/` 절대/상대 경로. sentence-transformers가 이
                   디렉토리에 `config.json`, `pytorch_model.bin` 또는 `model.safetensors`
                   등이 있다고 가정하고 `local_files_only=True`로 로드.
        device:    "cpu" | "cuda" | "auto". 기본 "cpu". "auto"는 torch.cuda.is_available()
                   기반. 런타임에 실패 시 "cpu" fallback + warning 로그.
        batch_size: embed_passages 내부 micro-batch 크기. 기본 32.
        normalize:  L2 정규화 여부. 기본 True (cosine=dot 등가).

    Raises:
        EmbedderError: 모델 로드 실패, 외부 네트워크 시도 탐지, config.json 누락.
    """

    def __init__(
        self,
        model_dir: str,
        device: str = "cpu",
        batch_size: int = 32,
        normalize: bool = True,
    ) -> None:
        # 오프라인 환경변수 강제 설정 (스펙 §4.5.1)
        os.environ.setdefault("HF_HUB_OFFLINE", "1")
        os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

        model_path = Path(model_dir)
        if not model_path.exists() or not (model_path / "config.json").exists():
            raise EmbedderError(f"bge-m3 model not found at {model_dir}")

        self._batch_size = batch_size
        self._normalize = normalize
        self._device = self._resolve_device(device)
        self._model: Any = None

        try:
            from sentence_transformers import SentenceTransformer

            self._model = SentenceTransformer(
                str(model_path),
                device=self._device,
                local_files_only=True,
                cache_folder=None,
            )
        except Exception as exc:
            raise EmbedderError(f"모델 로드 실패: {exc}") from exc

        logger.info("Embedder 초기화 완료: model_dir=%s, device=%s", model_dir, self._device)

    def _resolve_device(self, device: str) -> str:
        """device 문자열을 실제 사용 디바이스로 변환 (스펙 §4.5.2)."""
        if device == "cpu":
            return "cpu"
        if device == "cuda":
            try:
                import torch

                if not (torch.cuda.is_available() and torch.cuda.device_count() >= 1):
                    raise EmbedderError(
                        'device="cuda" 요청이나 CUDA 사용 불가. "cpu" 또는 "auto"를 사용하세요.'
                    )
                return "cuda"
            except ImportError as exc:
                raise EmbedderError("torch가 설치되지 않았습니다.") from exc
        if device == "auto":
            try:
                import torch

                if torch.cuda.is_available() and torch.cuda.device_count() >= 1:
                    logger.info("auto device: CUDA 감지 → cuda:0 사용")
                    return "cuda"
            except ImportError:
                pass
            logger.info("auto device: CUDA 미감지 → cpu 사용")
            return "cpu"
        # 알 수 없는 device 값은 그대로 전달 (sentence-transformers가 처리)
        return device

    def embed_passages(self, texts: list[str]) -> np.ndarray:
        """N개 passage를 (N, 1024) float32 배열로 변환.

        - 빈 리스트 입력 → shape (0, 1024) float32 empty 배열 반환(에러 아님).
        - normalize=True면 L2 norm=1.0 (±1e-6). normalize=False면 원본 벡터 반환.
        - text 중 빈 문자열("")이 있으면 해당 행은 " "(공백 1자)로 치환 후 임베딩.

        Raises:
            EmbedderError: 추론 실패(OOM, CUDA 에러 등). CPU fallback 시도 후에도 실패하면 raise.
        """
        if not texts:
            return np.empty((0, 1024), dtype=np.float32)

        # 빈 문자열 방어 처리
        sanitized = [t if t else " " for t in texts]

        try:
            output = self._try_encode(sanitized)
        except Exception as exc:
            # CUDA 실패 시 cpu fallback (auto 정책 포함)
            if self._device != "cpu":
                logger.warning("embed_passages CUDA 실패, CPU로 fallback: %s", exc)
                self._device = "cpu"
                try:
                    from sentence_transformers import SentenceTransformer

                    # 동일 모델을 cpu로 재로드 (모델 경로 추적)
                    self._model = SentenceTransformer(
                        self._model.model_name_or_path,
                        device="cpu",
                        local_files_only=True,
                        cache_folder=None,
                    )
                    output = self._try_encode(sanitized)
                except Exception as exc2:
                    raise EmbedderError(f"embed_passages CPU fallback도 실패: {exc2}") from exc2
            else:
                raise EmbedderError(f"embed_passages 추론 실패: {exc}") from exc

        result: np.ndarray = np.asarray(output, dtype=np.float32)

        if not np.isfinite(result).all():
            raise EmbedderError("embedder produced NaN/Inf")

        logger.debug("embed_passages: %d개 텍스트 → shape %s", len(texts), result.shape)
        return result

    def _try_encode(self, texts: list[str]) -> np.ndarray:
        """sentence-transformers encode 호출."""
        raw: Any = self._model.encode(
            texts,
            batch_size=self._batch_size,
            normalize_embeddings=self._normalize,
            convert_to_numpy=True,
        )
        # encode 반환이 numpy 배열인지 보장
        result: np.ndarray = np.asarray(raw, dtype=np.float32)
        return result

    def embed_query(self, text: str) -> np.ndarray:
        """단일 query → (1024,) float32 배열.

        빈 문자열 또는 공백만 → " "(공백 1자)로 치환 후 임베딩(방어적).
        """
        sanitized = text if text.strip() else " "
        passages: np.ndarray = self.embed_passages([sanitized])
        result: np.ndarray = passages[0]
        return result
