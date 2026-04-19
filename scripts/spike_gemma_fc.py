"""
Spike: Gemma 4 E4B Function Calling 정확도 측정
Usage: /mnt/c/projects/ai-assistant/.venv/bin/python scripts/spike_gemma_fc.py
"""

import json
import logging
import os
import sys
import time
from typing import Any

import requests

# ---------------------------------------------------------------------------
# 로깅 설정
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL = "http://192.168.219.109:11434"
OLLAMA_CHAT_URL = f"{OLLAMA_BASE_URL}/v1/chat/completions"
MODEL = "gemma4:e4b"
TODAY = "2026-04-18"
TIMEOUT_SECONDS = 120
OUTPUT_PATH = "/mnt/c/projects/ai-assistant/docs/research/gemma_function_calling_spike.md"

# ---------------------------------------------------------------------------
# 도구 정의
# ---------------------------------------------------------------------------
tools: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "add_event",
            "description": "일정을 캘린더에 추가한다",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "일정 제목"},
                    "start": {
                        "type": "string",
                        "description": "시작 시간 (ISO 8601, 예: 2026-04-18T15:00:00)",
                    },
                    "duration_minutes": {
                        "type": "integer",
                        "description": "소요 시간(분)",
                    },
                },
                "required": ["title", "start", "duration_minutes"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "특정 도시의 현재 날씨를 조회한다",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "도시 이름"},
                    "unit": {
                        "type": "string",
                        "enum": ["celsius", "fahrenheit"],
                        "description": "온도 단위",
                    },
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_docs",
            "description": "사내 문서에서 내용을 검색한다",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "검색어"},
                    "top_k": {
                        "type": "integer",
                        "description": "반환할 결과 수 (기본값 3)",
                    },
                },
                "required": ["query"],
            },
        },
    },
]

# ---------------------------------------------------------------------------
# 테스트 케이스
# ---------------------------------------------------------------------------
test_cases: list[dict[str, Any]] = [
    # add_event (4개)
    {
        "id": 1,
        "prompt": "내일 오후 3시에 마케팅 팀 회의 있어. 한 시간짜리야.",
        "expected_func": "add_event",
        "expected_args": {
            "title": "마케팅 팀 회의",
            "start": "2026-04-19T15:00:00",
            "duration_minutes": 60,
        },
    },
    {
        "id": 2,
        "prompt": "오늘 오전 10시에 인사팀이랑 면담 30분 잡아줘.",
        "expected_func": "add_event",
        "expected_args": {
            "title_contains": "면담",
            "start": "2026-04-18T10:00:00",
            "duration_minutes": 30,
        },
    },
    {
        "id": 3,
        "prompt": "다음 월요일 오전 9시에 주간 보고 미팅 등록해줘. 2시간이야.",
        "expected_func": "add_event",
        "expected_args": {"start": "2026-04-20T09:00:00", "duration_minutes": 120},
    },
    {
        "id": 4,
        "prompt": "4월 25일 오후 2시에 고객사 프레젠테이션 90분 일정 추가해.",
        "expected_func": "add_event",
        "expected_args": {"start": "2026-04-25T14:00:00", "duration_minutes": 90},
    },
    # get_weather (3개)
    {
        "id": 5,
        "prompt": "서울 날씨 어때?",
        "expected_func": "get_weather",
        "expected_args": {"city_contains": "서울"},
    },
    {
        "id": 6,
        "prompt": "부산 지금 비 오나? 섭씨로 알려줘.",
        "expected_func": "get_weather",
        "expected_args": {"city_contains": "부산", "unit": "celsius"},
    },
    {
        "id": 7,
        "prompt": "오늘 제주도 기온 알려줘.",
        "expected_func": "get_weather",
        "expected_args": {"city_contains": "제주"},
    },
    # search_docs (3개)
    {
        "id": 8,
        "prompt": "휴가 신청 절차 문서 찾아줘.",
        "expected_func": "search_docs",
        "expected_args": {"query_contains": "휴가"},
    },
    {
        "id": 9,
        "prompt": "작년 4분기 매출 보고서 검색해줘. 결과 5개만.",
        "expected_func": "search_docs",
        "expected_args": {"query_contains": "매출", "top_k": 5},
    },
    {
        "id": 10,
        "prompt": "보안 정책 관련 문서 있어?",
        "expected_func": "search_docs",
        "expected_args": {"query_contains": "보안"},
    },
]

SYSTEM_PROMPT = f"""오늘 날짜는 {TODAY}(토요일)이다.
다음 주 월요일은 2026-04-20이다.
사용자의 요청에 맞는 함수를 호출하라. 함수 호출이 필요 없는 경우에만 일반 텍스트로 답하라.
날짜·시간은 반드시 ISO 8601 형식(예: 2026-04-19T15:00:00)으로 기입하라."""


# ---------------------------------------------------------------------------
# 채점 함수
# ---------------------------------------------------------------------------
def check_arg_match(key: str, expected_val: Any, actual_args: dict[str, Any]) -> bool:
    """
    key가 '_contains' 접미사를 가지면 contains 검사, 아니면 exact match.
    실제 args 키는 접미사 제거 후 참조한다.
    """
    if key.endswith("_contains"):
        base_key = key[: -len("_contains")]
        actual_val = actual_args.get(base_key, "")
        return isinstance(actual_val, str) and str(expected_val) in actual_val
    else:
        actual_val = actual_args.get(key)
        # 정수 비교 시 문자열로 전달된 경우도 허용
        if isinstance(expected_val, int):
            try:
                return int(actual_val) == expected_val  # type: ignore[arg-type]
            except (TypeError, ValueError):
                return False
        return actual_val == expected_val


def score_case(
    tc: dict[str, Any],
    called_func: str | None,
    called_args: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    단일 테스트 케이스를 채점하고 점수 dict 반환.
    """
    expected_func: str = tc["expected_func"]
    expected_args: dict[str, Any] = tc["expected_args"]

    func_correct = int(called_func == expected_func)

    if called_args is None:
        called_args = {}

    # 필수 인자 (required fields)
    tool_def = next((t for t in tools if t["function"]["name"] == expected_func), None)
    required_fields: list[str] = []
    if tool_def:
        required_fields = tool_def["function"]["parameters"].get("required", [])

    required_present = int(
        all(f in called_args for f in required_fields) if called_func == expected_func else False
    )

    # 인자 값 정확도
    total_expected = len(expected_args)
    if total_expected == 0:
        arg_accuracy = 1.0
    else:
        matched = sum(1 for k, v in expected_args.items() if check_arg_match(k, v, called_args))
        arg_accuracy = matched / total_expected

    return {
        "func_correct": func_correct,
        "required_present": required_present,
        "arg_accuracy": arg_accuracy,
        "called_func": called_func,
        "called_args": called_args,
    }


# ---------------------------------------------------------------------------
# API 호출
# ---------------------------------------------------------------------------
def call_ollama(prompt: str) -> dict[str, Any]:
    """
    Ollama OpenAI 호환 엔드포인트에 tool call 요청을 보내고 응답을 반환.
    """
    payload: dict[str, Any] = {
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "tools": tools,
        "tool_choice": "auto",
        "stream": False,
    }

    response = requests.post(
        OLLAMA_CHAT_URL,
        json=payload,
        timeout=TIMEOUT_SECONDS,
        headers={"Content-Type": "application/json"},
    )
    response.raise_for_status()
    return response.json()  # type: ignore[no-any-return]


def extract_tool_call(
    response: dict[str, Any],
) -> tuple[str | None, dict[str, Any] | None]:
    """
    응답에서 (함수명, 인자 dict)를 추출. 없으면 (None, None).
    """
    choices = response.get("choices", [])
    if not choices:
        return None, None

    message = choices[0].get("message", {})
    tool_calls = message.get("tool_calls")

    if not tool_calls:
        return None, None

    first_call = tool_calls[0]
    func_name: str = first_call.get("function", {}).get("name", "")
    raw_args: str | dict[str, Any] = first_call.get("function", {}).get("arguments", "{}")

    if isinstance(raw_args, str):
        try:
            args: dict[str, Any] = json.loads(raw_args)
        except json.JSONDecodeError:
            logger.warning("인자 JSON 파싱 실패: %s", raw_args)
            args = {}
    else:
        args = raw_args

    return func_name or None, args


# ---------------------------------------------------------------------------
# 메인
# ---------------------------------------------------------------------------
def run_spike() -> None:
    logger.info("=== Gemma 4 E4B Function Calling Spike 시작 ===")
    logger.info("엔드포인트: %s", OLLAMA_CHAT_URL)
    logger.info("모델: %s", MODEL)

    results: list[dict[str, Any]] = []
    raw_responses: list[dict[str, Any]] = []
    tool_api_support: str = "UNKNOWN"

    for tc in test_cases:
        tc_id: int = tc["id"]
        prompt: str = tc["prompt"]
        logger.info("[%d/10] 프롬프트: %s", tc_id, prompt)

        called_func: str | None = None
        called_args: dict[str, Any] | None = None
        error_note: str = ""
        raw_resp: dict[str, Any] | None = None

        try:
            raw_resp = call_ollama(prompt)
            raw_responses.append({"id": tc_id, "prompt": prompt, "response": raw_resp})

            # tool call 지원 여부 감지
            body_str = json.dumps(raw_resp)
            if "does not support tools" in body_str.lower():
                logger.error("모델이 tool call을 지원하지 않는다고 응답함.")
                tool_api_support = "NO"
                error_note = "does not support tools"
            else:
                called_func, called_args = extract_tool_call(raw_resp)
                if called_func is None:
                    # tool_calls 필드 자체가 없는지 vs 빈 배열인지 구분
                    choices = raw_resp.get("choices", [])
                    message = choices[0].get("message", {}) if choices else {}
                    if "tool_calls" not in message:
                        if tool_api_support == "UNKNOWN":
                            tool_api_support = "PARTIAL"
                        error_note = "tool_calls 필드 없음 (일반 텍스트 응답)"
                    else:
                        if tool_api_support == "UNKNOWN":
                            tool_api_support = "YES"
                        error_note = "tool_calls 빈 배열 (함수 미호출)"
                else:
                    if tool_api_support == "UNKNOWN":
                        tool_api_support = "YES"

        except requests.exceptions.Timeout:
            error_note = f"타임아웃 ({TIMEOUT_SECONDS}s)"
            logger.warning("[%d] 타임아웃", tc_id)
        except requests.exceptions.ConnectionError as exc:
            error_note = f"연결 오류: {exc}"
            logger.error("[%d] 연결 오류: %s", tc_id, exc)
        except requests.exceptions.HTTPError as exc:
            resp_text = exc.response.text if exc.response is not None else ""
            if "does not support tools" in resp_text.lower():
                tool_api_support = "NO"
                error_note = "does not support tools (HTTP 에러)"
                logger.error("[%d] tool call 미지원 HTTP 에러", tc_id)
            else:
                error_note = f"HTTP 오류: {exc} | {resp_text[:200]}"
                logger.error("[%d] HTTP 오류: %s", tc_id, exc)
        except Exception as exc:  # noqa: BLE001
            error_note = f"예외: {exc}"
            logger.error("[%d] 예외: %s", tc_id, exc)

        scores = score_case(tc, called_func, called_args)

        results.append(
            {
                "id": tc_id,
                "prompt": prompt,
                "expected_func": tc["expected_func"],
                "called_func": called_func,
                "called_args": called_args,
                "func_correct": scores["func_correct"],
                "required_present": scores["required_present"],
                "arg_accuracy": scores["arg_accuracy"],
                "error_note": error_note,
            }
        )

        logger.info(
            "[%d] 함수=%s | 정확=%s | 인자정확도=%.0f%% | 비고=%s",
            tc_id,
            called_func,
            "O" if scores["func_correct"] else "X",
            scores["arg_accuracy"] * 100,
            error_note or "-",
        )

        # 에러 누적 방지: tool call 완전 미지원이면 이후 케이스 스킵
        if tool_api_support == "NO":
            logger.warning("tool call 미지원 확정. 나머지 케이스를 FAIL로 처리한다.")
            for remaining in test_cases[tc_id:]:
                results.append(
                    {
                        "id": remaining["id"],
                        "prompt": remaining["prompt"],
                        "expected_func": remaining["expected_func"],
                        "called_func": None,
                        "called_args": None,
                        "func_correct": 0,
                        "required_present": 0,
                        "arg_accuracy": 0.0,
                        "error_note": "does not support tools (스킵)",
                    }
                )
            break

        time.sleep(0.5)  # 서버 부하 완화

    # ---------------------------------------------------------------------------
    # 집계
    # ---------------------------------------------------------------------------
    total = len(results)
    func_correct_total = sum(r["func_correct"] for r in results)
    arg_accuracy_avg = sum(r["arg_accuracy"] for r in results) / total if total > 0 else 0.0
    overall_score = (
        (func_correct_total / total * 0.5 + arg_accuracy_avg * 0.5) if total > 0 else 0.0
    )

    logger.info("=== 집계 ===")
    logger.info("함수 선택 정확도: %d/%d", func_correct_total, total)
    logger.info("인자 정확도 평균: %.1f%%", arg_accuracy_avg * 100)
    logger.info("전체 점수(함수50+인자50): %.1f%%", overall_score * 100)

    # ---------------------------------------------------------------------------
    # 샘플 3개 선정 (성공 1, 부분 성공 1, 실패 1)
    # ---------------------------------------------------------------------------
    success_sample = next(
        (r for r in results if r["func_correct"] == 1 and r["arg_accuracy"] >= 0.8), None
    )
    partial_sample = next(
        (r for r in results if r["func_correct"] == 1 and 0.0 < r["arg_accuracy"] < 0.8),
        None,
    )
    # 부분 성공이 없으면 func_correct==1이지만 arg_accuracy 낮은 것
    if partial_sample is None:
        partial_sample = next(
            (r for r in results if r["func_correct"] == 1 and r != success_sample),
            None,
        )
    fail_sample = next((r for r in results if r["func_correct"] == 0), None)

    def format_sample(r: dict[str, Any] | None, label: str) -> str:
        if r is None:
            return f"### {label}\n해당 케이스 없음\n"
        raw = next((x for x in raw_responses if x["id"] == r["id"]), None)
        resp_str = (
            json.dumps(raw["response"], ensure_ascii=False, indent=2)[:800]
            if raw
            else "(응답 없음)"
        )
        return (
            f"### {label}\n"
            f"- 프롬프트: {r['prompt']}\n"
            f"- 기대 함수: `{r['expected_func']}`\n"
            f"- 호출 함수: `{r['called_func']}`\n"
            f"- 호출 인자: `{json.dumps(r['called_args'], ensure_ascii=False)}`\n"
            f"- 함수 선택: {'O' if r['func_correct'] else 'X'} | "
            f"인자 정확도: {r['arg_accuracy'] * 100:.0f}%\n"
            f"- 비고: {r['error_note'] or '-'}\n"
            f"\n<details><summary>원본 응답 (첫 800자)</summary>\n\n```json\n{resp_str}\n```\n</details>\n"
        )

    # ---------------------------------------------------------------------------
    # 마크다운 생성
    # ---------------------------------------------------------------------------
    table_rows: list[str] = []
    for r in results:
        func_icon = "O" if r["func_correct"] else "X"
        arg_pct = f"{r['arg_accuracy'] * 100:.0f}%"
        note = r["error_note"] or "-"
        table_rows.append(
            f"| {r['id']} | {r['prompt']} | `{r['expected_func']}` | "
            f"`{r['called_func'] or '-'}` | {func_icon} | {arg_pct} | {note} |"
        )

    judgment_threshold = 0.80
    judgment = (
        "네이티브 function calling 채택 가능"
        if overall_score >= judgment_threshold
        else "fallback 방식 검토 필요"
    )

    md = f"""# Spike: Gemma 4 E4B Function Calling 정확도

## 환경
- 모델: {MODEL} (Ollama @ {OLLAMA_BASE_URL})
- 테스트 날짜: {TODAY}
- tool call API 지원: {tool_api_support}

## 테스트 결과

| # | 프롬프트 | 기대 함수 | 호출 함수 | 함수 선택 | 인자 정확도 | 비고 |
|---|---|---|---|---|---|---|
{chr(10).join(table_rows)}

## 종합 점수
- 함수 선택 정확도: {func_correct_total}/{total}
- 인자 정확도 평균: {arg_accuracy_avg * 100:.1f}%
- 전체 점수 (함수 선택 50% + 인자 정확도 50%): {overall_score * 100:.1f}%

## 판정
- 80% 이상: 네이티브 function calling 채택
- 80% 미만: fallback 방식 검토 필요

**결과: {judgment} ({overall_score * 100:.1f}%)**

## 실제 응답 샘플 (대표 3개)

{format_sample(success_sample, "성공 케이스")}

{format_sample(partial_sample, "부분 성공 케이스")}

{format_sample(fail_sample, "실패 케이스")}

## 결론
- tool call API 지원 여부: {tool_api_support}
- 전체 테스트 케이스 수: {total}
- 함수 선택 정확 케이스: {func_correct_total}건 ({func_correct_total / total * 100:.1f}%)
- 인자 정확도 평균: {arg_accuracy_avg * 100:.1f}%
- 전체 점수: {overall_score * 100:.1f}%
"""

    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(md)

    logger.info("결과 저장: %s", OUTPUT_PATH)
    logger.info("=== Spike 완료 ===")


if __name__ == "__main__":
    run_spike()
