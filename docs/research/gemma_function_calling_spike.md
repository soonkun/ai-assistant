# Spike: Gemma 4 E4B Function Calling 정확도

## 환경
- 모델: gemma4:e4b (Ollama @ http://192.168.219.109:11434)
- 테스트 날짜: 2026-04-18
- tool call API 지원: YES

## 테스트 결과

| # | 프롬프트 | 기대 함수 | 호출 함수 | 함수 선택 | 인자 정확도 | 비고 |
|---|---|---|---|---|---|---|
| 1 | 내일 오후 3시에 마케팅 팀 회의 있어. 한 시간짜리야. | `add_event` | `add_event` | O | 100% | - |
| 2 | 오늘 오전 10시에 인사팀이랑 면담 30분 잡아줘. | `add_event` | `add_event` | O | 100% | - |
| 3 | 다음 월요일 오전 9시에 주간 보고 미팅 등록해줘. 2시간이야. | `add_event` | `add_event` | O | 100% | - |
| 4 | 4월 25일 오후 2시에 고객사 프레젠테이션 90분 일정 추가해. | `add_event` | `add_event` | O | 100% | - |
| 5 | 서울 날씨 어때? | `get_weather` | `get_weather` | O | 100% | - |
| 6 | 부산 지금 비 오나? 섭씨로 알려줘. | `get_weather` | `get_weather` | O | 100% | - |
| 7 | 오늘 제주도 기온 알려줘. | `get_weather` | `get_weather` | O | 100% | - |
| 8 | 휴가 신청 절차 문서 찾아줘. | `search_docs` | `search_docs` | O | 100% | - |
| 9 | 작년 4분기 매출 보고서 검색해줘. 결과 5개만. | `search_docs` | `search_docs` | O | 100% | - |
| 10 | 보안 정책 관련 문서 있어? | `search_docs` | `search_docs` | O | 100% | - |

## 종합 점수
- 함수 선택 정확도: 10/10
- 인자 정확도 평균: 100.0%
- 전체 점수 (함수 선택 50% + 인자 정확도 50%): 100.0%

## 판정
- 80% 이상: 네이티브 function calling 채택
- 80% 미만: fallback 방식 검토 필요

**결과: 네이티브 function calling 채택 가능 (100.0%)**

## 실제 응답 샘플 (대표 3개)

### 성공 케이스
- 프롬프트: 내일 오후 3시에 마케팅 팀 회의 있어. 한 시간짜리야.
- 기대 함수: `add_event`
- 호출 함수: `add_event`
- 호출 인자: `{"duration_minutes": 60, "start": "2026-04-19T15:00:00", "title": "마케팅 팀 회의"}`
- 함수 선택: O | 인자 정확도: 100%
- 비고: -

<details><summary>원본 응답 (첫 800자)</summary>

```json
{
  "id": "chatcmpl-618",
  "object": "chat.completion",
  "created": 1776449216,
  "model": "gemma4:e4b",
  "system_fingerprint": "fp_ollama",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "",
        "reasoning": "1. **Analyze the Request:** The user wants to schedule a meeting (\"마케팅 팀 회의\") for \"tomorrow at 3 PM\" and it will last for \"one hour.\"\n\n2. **Determine Necessary Tools:** The available tools are `add_event`, `get_weather`, and `search_docs`. Scheduling an event requires `add_event`.\n\n3. **Identify Parameters for `add_event`:**\n    *   `title`: \"마케팅 팀 회의\" (Marketing Team Meeting)\n    *   `start`: \"내일 오후 3시\" (Tomorrow at 3 PM)\n    *   `duration_minutes`: \"한 시간\" (60 minutes)\n\n4. **Calculate/Determine Da
```
</details>


### 부분 성공 케이스
- 프롬프트: 오늘 오전 10시에 인사팀이랑 면담 30분 잡아줘.
- 기대 함수: `add_event`
- 호출 함수: `add_event`
- 호출 인자: `{"duration_minutes": 30, "start": "2026-04-18T10:00:00", "title": "인사팀이랑 면담"}`
- 함수 선택: O | 인자 정확도: 100%
- 비고: -

<details><summary>원본 응답 (첫 800자)</summary>

```json
{
  "id": "chatcmpl-641",
  "object": "chat.completion",
  "created": 1776449247,
  "model": "gemma4:e4b",
  "system_fingerprint": "fp_ollama",
  "choices": [
    {
      "index": 0,
      "message": {
        "role": "assistant",
        "content": "",
        "reasoning": "The user wants to schedule a meeting (\"인사팀이랑 면담\") today at 10:00 AM for 30 minutes.\n\n1.  **Identify the tool:** The `add_event` tool is suitable for scheduling an event.\n2.  **Determine the parameters:**\n    *   `title`: \"인사팀이랑 면담\" (Meeting with HR team)\n    *   `start`: Today's date at 10:00 AM. The current date is 2026-04-18. So, the start time is \"2026-04-18T10:00:00\".\n    *   `duration_minutes`: 30 minutes.\n3.  **Construct the function call:** Call `add_event` with the identified parameters.",
        
```
</details>


### 실패 케이스
해당 케이스 없음


## 결론
- tool call API 지원 여부: YES
- 전체 테스트 케이스 수: 10
- 함수 선택 정확 케이스: 10건 (100.0%)
- 인자 정확도 평균: 100.0%
- 전체 점수: 100.0%
