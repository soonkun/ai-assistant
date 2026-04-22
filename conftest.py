# conftest.py
"""최상위 pytest conftest — src와 upstream을 sys.path에 추가.

tests/app/__init__.py가 pytest에 의해 'app' 패키지로 인식되는 문제를 해결하기 위해
sys.path를 먼저 설정하고 src/app을 올바른 'app' 패키지로 등록.
"""

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

_PROJECT_ROOT = Path(__file__).parent

# src 디렉토리 (가장 앞에 추가하여 우선순위 확보)
_SRC = _PROJECT_ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# upstream/Open-LLM-VTuber/src (open_llm_vtuber 패키지)
_UPSTREAM_SRC = _PROJECT_ROOT / "upstream" / "Open-LLM-VTuber" / "src"
if str(_UPSTREAM_SRC) not in sys.path:
    sys.path.insert(1, str(_UPSTREAM_SRC))

# upstream/Open-LLM-VTuber (prompts 등 루트 패키지)
_UPSTREAM_ROOT = _PROJECT_ROOT / "upstream" / "Open-LLM-VTuber"
if str(_UPSTREAM_ROOT) not in sys.path:
    sys.path.insert(2, str(_UPSTREAM_ROOT))


# upstream의 선택적 의존성을 mock으로 등록 (테스트 환경에서 설치되지 않은 패키지들)
def _make_mock_package(name: str) -> MagicMock:
    """서브모듈 접근이 가능한 mock 패키지 생성."""
    from importlib.machinery import ModuleSpec

    mock = MagicMock()
    mock.__name__ = name
    mock.__package__ = name
    mock.__path__ = []  # 패키지로 인식되도록
    # __spec__=None이면 importlib.util.find_spec이 ValueError를 던진다.
    # transformers._is_package_available 등이 find_spec으로 설치 여부만 체크할 때
    # ValueError가 예외 전파되는 문제를 피하기 위해 최소 ModuleSpec을 부여한다.
    mock.__spec__ = ModuleSpec(name, loader=None)
    return mock


_MOCK_PACKAGES = [
    "letta_client",
    "mem0",
    "hume",
    "aiohttp",
    "pydub",
    "pydub.utils",
    "faster_whisper",
    "torch",
    "torchaudio",
    "torchaudio.transforms",
    "silero_vad",
    "onnxruntime",
    # M_04 TTS — 실제 라이브러리가 설치되지 않은 환경에서 mock 등록
    "melo",
    "melo.api",
    "TTS",
    "TTS.api",
    "soundfile",
    # M_05 LLMAgent — anthropic SDK는 사용 안 하지만 upstream import가 요구
    "anthropic",
]
for _pkg in _MOCK_PACKAGES:
    if _pkg in sys.modules:
        continue
    # 실제 venv에 설치된 패키지는 mock으로 덮지 않는다.
    # find_spec이 ValueError를 던지는 경우(sys.modules에 __spec__=None인 가짜가 있을 때)는
    # except로 흡수하고 mock 경로로 진행.
    try:
        if importlib.util.find_spec(_pkg) is not None:
            continue
    except (ImportError, ValueError):
        pass
    _mock = _make_mock_package(_pkg)
    sys.modules[_pkg] = _mock  # type: ignore[assignment]

# tests/app/__init__.py가 pytest에 의해 'app' 패키지로 잘못 인식되는 것을 방지.
# src/app을 올바른 'app' 모듈로 sys.modules에 미리 등록.
if "app" not in sys.modules:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "app",
        str(_SRC / "app" / "__init__.py"),
        submodule_search_locations=[str(_SRC / "app")],
    )
    if spec and spec.loader:
        _app_module = importlib.util.module_from_spec(spec)
        sys.modules["app"] = _app_module
        spec.loader.exec_module(_app_module)  # type: ignore[union-attr]

# tests/vad/__init__.py가 pytest에 의해 'vad' 패키지로 잘못 인식되는 것을 방지.
# src/vad를 올바른 'vad' 모듈로 sys.modules에 미리 등록.
if "vad" not in sys.modules:
    import importlib.util as _importlib_util_vad

    _vad_spec = _importlib_util_vad.spec_from_file_location(
        "vad",
        str(_SRC / "vad" / "__init__.py"),
        submodule_search_locations=[str(_SRC / "vad")],
    )
    if _vad_spec and _vad_spec.loader:
        _vad_module = _importlib_util_vad.module_from_spec(_vad_spec)
        sys.modules["vad"] = _vad_module
        _vad_spec.loader.exec_module(_vad_module)  # type: ignore[union-attr]

# tests/asr/__init__.py가 pytest에 의해 'asr' 패키지로 잘못 인식되는 것을 방지.
# src/asr를 올바른 'asr' 모듈로 sys.modules에 미리 등록.
if "asr" not in sys.modules:
    import importlib.util as _importlib_util

    _asr_spec = _importlib_util.spec_from_file_location(
        "asr",
        str(_SRC / "asr" / "__init__.py"),
        submodule_search_locations=[str(_SRC / "asr")],
    )
    if _asr_spec and _asr_spec.loader:
        _asr_module = _importlib_util.module_from_spec(_asr_spec)
        sys.modules["asr"] = _asr_module
        _asr_spec.loader.exec_module(_asr_module)  # type: ignore[union-attr]

# tests/tts/__init__.py가 pytest에 의해 'tts' 패키지로 잘못 인식되는 것을 방지.
# src/tts를 올바른 'tts' 모듈로 sys.modules에 미리 등록.
if "tts" not in sys.modules:
    import importlib.util as _importlib_util_tts

    _tts_spec = _importlib_util_tts.spec_from_file_location(
        "tts",
        str(_SRC / "tts" / "__init__.py"),
        submodule_search_locations=[str(_SRC / "tts")],
    )
    if _tts_spec and _tts_spec.loader:
        _tts_module = _importlib_util_tts.module_from_spec(_tts_spec)
        sys.modules["tts"] = _tts_module
        _tts_spec.loader.exec_module(_tts_module)  # type: ignore[union-attr]
