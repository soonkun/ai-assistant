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
    # upstream Open-LLM-VTuber — git clone 없는 환경(macOS 개발 머신 등)에서 mock 등록
    "open_llm_vtuber",
    "open_llm_vtuber.asr",
    "open_llm_vtuber.asr.asr_interface",
    "open_llm_vtuber.tts",
    "open_llm_vtuber.tts.tts_interface",
    "open_llm_vtuber.agent",
    "open_llm_vtuber.agent.agents",
    "open_llm_vtuber.agent.agents.agent_interface",
    "open_llm_vtuber.agent.agents.basic_memory_agent",
    "open_llm_vtuber.agent.input_types",
    "open_llm_vtuber.agent.stateless_llm",
    "open_llm_vtuber.agent.stateless_llm.openai_compatible_llm",
    "open_llm_vtuber.config_manager",
    "open_llm_vtuber.config_manager.utils",
    "open_llm_vtuber.mcpp",
    "open_llm_vtuber.mcpp.tool_executor",
    "open_llm_vtuber.mcpp.tool_manager",
    "open_llm_vtuber.routes",
    "open_llm_vtuber.server",
    "open_llm_vtuber.service_context",
    "open_llm_vtuber.websocket_handler",
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


def _register_src_module(name: str) -> None:
    """tests/<name>/__init__.py가 pytest에 의해 '<name>' 패키지로 잘못 인식되는 것을 방지.

    src/<name>을 올바른 '<name>' 모듈로 sys.modules에 미리 등록한다.
    upstream 없는 개발 환경(macOS 등)에서 로드 실패 시 경고만 출력하고 계속 진행.
    """
    import importlib.util as _iu

    if name in sys.modules:
        return

    _spec = _iu.spec_from_file_location(
        name,
        str(_SRC / name / "__init__.py"),
        submodule_search_locations=[str(_SRC / name)],
    )
    if not (_spec and _spec.loader):
        return

    _mod = _iu.module_from_spec(_spec)
    sys.modules[name] = _mod
    try:
        _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
    except Exception as _exc:
        # upstream 미설치 환경에서 일부 src 모듈이 로드 실패할 수 있다.
        # 해당 모듈의 tests가 직접 실행될 때 import 오류가 다시 발생하므로
        # 여기서는 경고만 남기고 계속 진행한다.
        import warnings

        warnings.warn(
            f"conftest: src/{name} 모듈 사전 등록 실패 ({type(_exc).__name__}: {_exc}). "
            "해당 모듈 테스트는 import 오류가 날 수 있음.",
            stacklevel=2,
        )
        # 실패한 모듈을 sys.modules에 남겨두면 이후 import 시 혼란을 줄 수 있으므로 제거.
        sys.modules.pop(name, None)


for _src_mod_name in ("app", "vad", "asr", "tts"):
    _register_src_module(_src_mod_name)
